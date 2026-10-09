from fastapi.testclient import TestClient

from app import security
from app.main import app


def test_auth_config_is_public_and_does_not_advertise_api_key_login():
    client = TestClient(app)
    response = client.get("/api/v1/auth/config")
    assert response.status_code == 200
    payload = response.json()
    assert "api_key" not in payload
    assert payload["web_console"]["auto_login"] is True
    assert "oidc" in payload
    assert "ldap" in payload


def test_direct_api_still_requires_authentication():
    client = TestClient(app)
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401


def test_internal_web_console_session_is_non_admin(monkeypatch):
    monkeypatch.setattr(security, "ensure_rate_limit", lambda *args, **kwargs: None)
    client = TestClient(app)

    response = client.post("/internal/web-console/session")
    assert response.status_code == 200
    payload = response.json()
    assert payload["auth_source"] == "web-console"
    assert payload["roles"] == ["operator"]
    assert payload["is_admin"] is False
    assert "*" not in payload["scopes"]
    assert "pdfhub_session=" in response.headers.get("set-cookie", "")

    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["auth_source"] == "web-console"
    assert me.json()["is_admin"] is False


def test_cookie_session_authentication(monkeypatch):
    monkeypatch.setattr(security, "ensure_rate_limit", lambda *args, **kwargs: None)
    identity = {
        "name": "user:teacher",
        "subject": "teacher-1",
        "display_name": "Teacher",
        "groups": ["pdfhub-users"],
        "roles": ["operator"],
        "scopes": ["files:read"],
        "source": "oidc",
        "is_identity_admin": False,
    }
    from app.identity import create_session_token

    client = TestClient(app)
    client.cookies.set("pdfhub_session", create_session_token(identity))
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "user:teacher"
    assert payload["auth_source"] == "oidc"
    assert payload["roles"] == ["operator"]
    assert "files:read" in payload["scopes"]


def test_logout_clears_session_cookie():
    client = TestClient(app)
    response = client.post("/api/v1/auth/logout")
    assert response.status_code == 204
    assert "pdfhub_session=" in response.headers.get("set-cookie", "")



def test_effective_role_and_limits_are_self_scoped_and_stable(monkeypatch):
    from app.config import get_settings
    from app.identity import create_local_admin_identity, create_session_token
    settings = get_settings()
    monkeypatch.setattr(security, "ensure_rate_limit", lambda *args, **kwargs: None)
    local = TestClient(app)
    local.cookies.set("pdfhub_session", create_session_token(create_local_admin_identity("teacher-admin")))
    response = local.get("/api/v1/auth/me")
    assert response.status_code == 200
    identity = response.json()
    assert identity["roles"] == ["admin"]
    assert identity["auth_source"] == "local-admin"
    assert identity["rate_limit_per_minute"] == settings.default_rate_limit_per_minute
    assert identity["daily_job_limit"] == settings.default_daily_job_limit
    assert identity["max_storage_mb"] == settings.default_max_storage_mb
    assert identity["quota_exempt"] is False
    assert "password" not in response.text.lower()
    assert "api_key" not in identity

    bootstrap = TestClient(app)
    response = bootstrap.get("/api/v1/auth/me", headers={"X-API-Key": "pdfh_ci_admin_key_change_me"})
    assert response.status_code == 200
    assert response.json()["quota_exempt"] is True
    assert response.json()["daily_job_limit"] == 0
