import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import ApiKey
from app.policy import effective_policy, ensure_rate_limit

settings = get_settings()


@dataclass
class Principal:
    name: str
    scopes: set[str]
    is_bootstrap_admin: bool = False
    rate_limit_per_minute: int = 0
    daily_job_limit: int = 0
    max_storage_mb: int = 0


def hash_api_key(value: str) -> str:
    return hashlib.sha256((settings.api_key_pepper + value).encode("utf-8")).hexdigest()


def new_api_key() -> str:
    return "pdfh_" + secrets.token_urlsafe(32)


def _extract_key(authorization: str | None, x_api_key: str | None) -> str | None:
    if x_api_key:
        return x_api_key.strip()
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return None


def get_principal(
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> Principal:
    supplied = _extract_key(authorization, x_api_key)
    if not supplied:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API key required")

    if hmac.compare_digest(supplied, settings.admin_api_key):
        return Principal(name="bootstrap-admin", scopes={"*"}, is_bootstrap_admin=True)

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
    )


def require_scope(scope: str) -> Callable:
    def dependency(principal: Principal = Depends(get_principal)) -> Principal:
        if "*" not in principal.scopes and scope not in principal.scopes:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Missing scope: {scope}")
        return principal

    return dependency
