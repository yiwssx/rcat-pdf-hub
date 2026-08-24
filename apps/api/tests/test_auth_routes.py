from fastapi.testclient import TestClient

from app import security
from app.main import app


def test_auth_config_is_public():
    client = TestClient(app)
    response = client.get("/api/v1/auth/config")
    assert response.status_code == 200
    payload = response.json()
    assert payload["api_key"]["enabled"] is True
    assert "oidc" in payload
    assert "ldap" in payload


def test_cookie_session_authentication(monkeypatch):
    monkeypatch.setattr(security, "ensure_rate_limit", lambda *args, **kwargs: None)
    identity = {
        "name": "user:teacher",
        "subject": "teacher-1",
        "display_name": "Teacher",
        "groups": ["teachers"],
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
    assert payload["scopes"] == ["files:read"]


def test_logout_clears_session_cookie():
    client = TestClient(app)
    response = client.post("/api/v1/auth/logout")
    assert response.status_code == 204
    assert "pdfhub_session=" in response.headers.get("set-cookie", "")
