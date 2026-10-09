import hmac
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import RedirectResponse
from ldap3.core.exceptions import LDAPException

from app.audit import audit_event
from app.config import get_settings
from app.identity import (
    authenticate_ldap,
    build_oidc_authorization_url,
    complete_oidc_callback,
    create_local_admin_identity,
    create_session_token,
    public_auth_config,
)
from app.passwords import verify_password
from app.policy import ensure_rate_limit
from app.schemas import AuthMeOut, LdapLoginRequest, LocalLoginRequest
from app.security import Principal, get_principal

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
settings = get_settings()


def _set_session_cookie(response: Response, identity: dict) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=create_session_token(identity),
        max_age=settings.session_ttl_minutes * 60,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )


def _me(principal: Principal) -> AuthMeOut:
    return AuthMeOut(
        name=principal.name,
        display_name=principal.display_name,
        subject=principal.subject,
        scopes=sorted(principal.scopes),
        groups=sorted(principal.groups),
        roles=sorted(principal.roles),
        auth_source=principal.auth_source,
        is_admin=principal.is_bootstrap_admin or principal.is_identity_admin or "*" in principal.scopes,
        rate_limit_per_minute=principal.rate_limit_per_minute,
        daily_job_limit=principal.daily_job_limit,
        max_storage_mb=principal.max_storage_mb,
        quota_exempt=principal.is_bootstrap_admin,
    )


@router.get("/config")
def auth_config():
    return public_auth_config()


@router.get("/me", response_model=AuthMeOut)
def me(principal: Principal = Depends(get_principal)):
    return _me(principal)


@router.get("/oidc/login")
def oidc_login(return_to: str = Query(default="/", max_length=2048)):
    if not settings.oidc_enabled:
        raise HTTPException(status_code=404, detail="OIDC is disabled")
    try:
        return RedirectResponse(build_oidc_authorization_url(return_to), status_code=302)
    except Exception as exc:
        audit_event("auth.oidc_failed", "anonymous", "identity", None, {"stage": "login", "error": str(exc)[-1000:]})
        raise HTTPException(status_code=502, detail="OIDC provider is unavailable") from exc


@router.get("/oidc/callback")
def oidc_callback(code: str, state: str):
    if not settings.oidc_enabled:
        raise HTTPException(status_code=404, detail="OIDC is disabled")
    try:
        identity, return_to = complete_oidc_callback(code, state)
    except Exception as exc:
        audit_event("auth.oidc_failed", "anonymous", "identity", None, {"stage": "callback", "error": str(exc)[-1000:]})
        raise HTTPException(status_code=401, detail="OIDC authentication failed") from exc
    response = RedirectResponse(return_to, status_code=302)
    _set_session_cookie(response, identity)
    audit_event("auth.login", identity["name"], "identity", identity["subject"], {"source": "oidc"})
    return response




@router.post("/local/login", response_model=AuthMeOut)
def local_login(req: LocalLoginRequest, response: Response):
    if not settings.local_admin_enabled:
        raise HTTPException(status_code=404, detail="Local admin login is disabled")
    ensure_rate_limit(f"local-login:{req.username[:80]}", 10)
    username_ok = hmac.compare_digest(req.username.strip(), settings.local_admin_username.strip())
    password_ok = verify_password(req.password, settings.local_admin_password_hash) if username_ok else False
    if not (username_ok and password_ok):
        audit_event("auth.local_failed", f"local:{req.username[:80]}", "identity", None, {})
        raise HTTPException(status_code=401, detail="Local admin authentication failed")
    identity = create_local_admin_identity(settings.local_admin_username)
    _set_session_cookie(response, identity)
    audit_event("auth.login", identity["name"], "identity", identity["subject"], {"source": "local-admin"})
    return AuthMeOut(
        name=identity["name"],
        display_name=identity["display_name"],
        subject=identity["subject"],
        scopes=identity["scopes"],
        groups=identity["groups"],
        roles=identity["roles"],
        auth_source="local-admin",
        is_admin=True,
        rate_limit_per_minute=settings.default_rate_limit_per_minute,
        daily_job_limit=settings.default_daily_job_limit,
        max_storage_mb=settings.default_max_storage_mb,
    )


@router.post("/ldap/login", response_model=AuthMeOut)
def ldap_login(req: LdapLoginRequest, response: Response):
    if not settings.ldap_enabled:
        raise HTTPException(status_code=404, detail="LDAP is disabled")
    try:
        identity = authenticate_ldap(req.username, req.password)
    except (LDAPException, ValueError) as exc:
        audit_event("auth.ldap_failed", f"ldap:{req.username}", "identity", None, {"error": str(exc)[-500:]})
        raise HTTPException(status_code=401, detail="LDAP authentication failed") from exc
    _set_session_cookie(response, identity)
    audit_event("auth.login", identity["name"], "identity", identity["subject"], {"source": "ldap"})
    return AuthMeOut(
        name=identity["name"],
        display_name=identity.get("display_name"),
        subject=identity.get("subject"),
        scopes=sorted(identity.get("scopes", [])),
        groups=sorted(identity.get("groups", [])),
        roles=sorted(identity.get("roles", [])),
        auth_source="ldap",
        is_admin=bool(identity.get("is_identity_admin")) or "*" in set(identity.get("scopes", [])),
        rate_limit_per_minute=settings.default_rate_limit_per_minute,
        daily_job_limit=settings.default_daily_job_limit,
        max_storage_mb=settings.default_max_storage_mb,
    )


@router.post("/logout", status_code=204)
def logout():
    response = Response(status_code=204)
    response.delete_cookie(settings.session_cookie_name, path="/")
    return response
