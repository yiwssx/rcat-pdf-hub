from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import RedirectResponse
from ldap3.core.exceptions import LDAPException

from app.audit import audit_event
from app.config import get_settings
from app.identity import (
    authenticate_ldap,
    authenticate_local,
    build_oidc_authorization_url,
    complete_oidc_callback,
    create_session_token,
    public_auth_config,
)
from app.principal_id import principal_name_for_identity
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
        auth_source=principal.auth_source,
        is_admin=principal.is_bootstrap_admin or principal.is_identity_admin or "*" in principal.scopes,
    )


@router.get("/config")
def auth_config():
    return public_auth_config()


@router.get("/me", response_model=AuthMeOut)
def me(principal: Principal = Depends(get_principal)):
    return _me(principal)


@router.post("/local/login", response_model=AuthMeOut)
def local_login(req: LocalLoginRequest, response: Response):
    if not settings.local_auth_enabled:
        raise HTTPException(status_code=404, detail="Local authentication is disabled")
    try:
        identity = authenticate_local(req.username, req.password)
        principal_name = principal_name_for_identity(identity)
    except ValueError as exc:
        audit_event("auth.local_failed", "local:anonymous", "identity", None, {"error": "invalid credentials"})
        raise HTTPException(status_code=401, detail="Local authentication failed") from exc
    _set_session_cookie(response, identity)
    audit_event("auth.login", principal_name, "identity", identity["subject"], {"source": "local"})
    return AuthMeOut(
        name=principal_name,
        display_name=identity.get("display_name"),
        subject=identity.get("subject"),
        scopes=sorted(identity.get("scopes", [])),
        groups=sorted(identity.get("groups", [])),
        auth_source="local",
        is_admin=True,
    )


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
        principal_name = principal_name_for_identity(identity)
    except Exception as exc:
        audit_event("auth.oidc_failed", "anonymous", "identity", None, {"stage": "callback", "error": str(exc)[-1000:]})
        raise HTTPException(status_code=401, detail="OIDC authentication failed") from exc
    response = RedirectResponse(return_to, status_code=302)
    _set_session_cookie(response, identity)
    audit_event("auth.login", principal_name, "identity", identity["subject"], {"source": "oidc"})
    return response


@router.post("/ldap/login", response_model=AuthMeOut)
def ldap_login(req: LdapLoginRequest, response: Response):
    if not settings.ldap_enabled:
        raise HTTPException(status_code=404, detail="LDAP is disabled")
    try:
        identity = authenticate_ldap(req.username, req.password)
        principal_name = principal_name_for_identity(identity)
    except (LDAPException, ValueError) as exc:
        audit_event("auth.ldap_failed", f"ldap:{req.username}", "identity", None, {"error": str(exc)[-500:]})
        raise HTTPException(status_code=401, detail="LDAP authentication failed") from exc
    _set_session_cookie(response, identity)
    audit_event("auth.login", principal_name, "identity", identity["subject"], {"source": "ldap"})
    return AuthMeOut(
        name=principal_name,
        display_name=identity.get("display_name"),
        subject=identity.get("subject"),
        scopes=sorted(identity.get("scopes", [])),
        groups=sorted(identity.get("groups", [])),
        auth_source="ldap",
        is_admin=bool(identity.get("is_identity_admin")) or "*" in set(identity.get("scopes", [])),
    )


@router.post("/logout", status_code=204)
def logout():
    response = Response(status_code=204)
    response.delete_cookie(settings.session_cookie_name, path="/")
    return response
