import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable

import httpx
import jwt
from fastapi import Cookie, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.identity import decode_session_token, identity_from_claims, validate_oidc_token
from app.models import ApiKey
from app.policy import effective_policy, ensure_rate_limit
from app.principal_id import principal_name_for_identity

settings = get_settings()


@dataclass
class Principal:
    name: str
    scopes: set[str]
    is_bootstrap_admin: bool = False
    is_identity_admin: bool = False
    rate_limit_per_minute: int = 0
    daily_job_limit: int = 0
    max_storage_mb: int = 0
    subject: str | None = None
    display_name: str | None = None
    groups: set[str] = field(default_factory=set)
    auth_source: str = "api_key"


def hash_api_key(value: str) -> str:
    return hashlib.sha256((settings.api_key_pepper + value).encode("utf-8")).hexdigest()


def new_api_key() -> str:
    return "pdfh_" + secrets.token_urlsafe(32)


def _service_principal(supplied: str, db: Session) -> Principal:
    if hmac.compare_digest(supplied, settings.admin_api_key):
        return Principal(
            name="bootstrap-admin",
            scopes={"*"},
            is_bootstrap_admin=True,
            is_identity_admin=True,
            auth_source="bootstrap",
        )

    digest = hash_api_key(supplied)
    record = db.scalar(select(ApiKey).where(ApiKey.key_hash == digest, ApiKey.active.is_(True)))
    if not record:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")

    policy = effective_policy(db, record.name)
    ensure_rate_limit(record.name, policy.rate_limit_per_minute)
    record.last_used_at = datetime.now(timezone.utc)
    db.commit()
    return Principal(
        name=record.name,
        scopes=set(json.loads(record.scopes_json)),
        rate_limit_per_minute=policy.rate_limit_per_minute,
        daily_job_limit=policy.daily_job_limit,
        max_storage_mb=policy.max_storage_mb,
        auth_source="api_key",
    )


def _identity_principal(identity: dict) -> Principal:
    scopes = set(identity.get("scopes") or [])
    name = principal_name_for_identity(identity)
    ensure_rate_limit(name, settings.default_rate_limit_per_minute)
    return Principal(
        name=name,
        scopes=scopes,
        is_identity_admin=bool(identity.get("is_identity_admin", False)),
        rate_limit_per_minute=settings.default_rate_limit_per_minute,
        daily_job_limit=settings.default_daily_job_limit,
        max_storage_mb=settings.default_max_storage_mb,
        subject=str(identity.get("subject") or ""),
        display_name=str(identity.get("display_name") or identity.get("name") or name),
        groups=set(identity.get("groups") or []),
        auth_source=str(identity.get("source") or "identity"),
    )


def _bearer_identity(token: str) -> Principal:
    try:
        return _identity_principal(decode_session_token(token))
    except jwt.PyJWTError:
        pass
    if settings.oidc_enabled:
        try:
            return _identity_principal(identity_from_claims(validate_oidc_token(token), "oidc-bearer"))
        except (jwt.PyJWTError, RuntimeError, ValueError, httpx.HTTPError) as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid bearer token") from exc
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid bearer token")


def get_principal(
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
    pdfhub_session: str | None = Cookie(default=None, alias=settings.session_cookie_name),
    db: Session = Depends(get_db),
) -> Principal:
    if x_api_key:
        return _service_principal(x_api_key.strip(), db)

    if authorization and authorization.lower().startswith("bearer "):
        supplied = authorization[7:].strip()
        if supplied.startswith("pdfh_") or hmac.compare_digest(supplied, settings.admin_api_key):
            return _service_principal(supplied, db)
        return _bearer_identity(supplied)

    if pdfhub_session:
        try:
            return _identity_principal(decode_session_token(pdfhub_session))
        except (jwt.PyJWTError, ValueError) as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired or invalid") from exc

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")


def require_scope(scope: str) -> Callable:
    def dependency(principal: Principal = Depends(get_principal)) -> Principal:
        if "*" not in principal.scopes and scope not in principal.scopes:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Missing scope: {scope}")
        return principal

    return dependency
