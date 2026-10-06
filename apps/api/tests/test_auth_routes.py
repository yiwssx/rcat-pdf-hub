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
