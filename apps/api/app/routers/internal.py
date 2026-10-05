from fastapi import APIRouter, HTTPException, Response, status

from app.audit import audit_event
from app.config import get_settings
from app.identity import create_session_token, create_web_console_identity
from app.schemas import AuthMeOut

router = APIRouter(prefix="/internal", tags=["internal"])
settings = get_settings()


@router.post("/web-console/session", response_model=AuthMeOut, include_in_schema=False)
def web_console_session(response: Response):
    if not settings.web_console_auto_login_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Web Console auto-login is disabled")

    identity = create_web_console_identity()
    response.set_cookie(
        key=settings.session_cookie_name,
        value=create_session_token(identity),
        max_age=settings.session_ttl_minutes * 60,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )
    audit_event(
        "auth.login",
        identity["name"],
        "identity",
        identity["subject"],
        {"source": "web-console"},
    )
    return AuthMeOut(
        name=identity["name"],
        display_name=identity["display_name"],
        subject=identity["subject"],
        scopes=sorted(identity["scopes"]),
        groups=[],
        auth_source="web-console",
        is_admin=False,
    )
