from fastapi.testclient import TestClient

from app import security
from app.main import app
from app.principal_id import principal_name_for_identity


def test_auth_config_is_public():
    client = TestClient(app)
    response = client.get("/api/v1/auth/config")
    assert response.status_code == 200
    payload = response.json()
    assert payload["api_key"]["enabled"] is True
    assert "local" in payload
    assert "oidc" in payload
    assert "ldap" in payload


def test_cookie_session_authentication_uses_stable_oidc_principal(monkeypatch):
    monkeypatch.setattr(security, "ensure_rate_limit", lambda *args, **kwargs: None)
    identity = {
        "name": "identity:oidc",
        "subject": "teacher-1",
        "display_name": "Teacher",
        "groups": ["teachers"],
        "scopes": ["files:read"],
        "source": "oidc",
        "issuer": "https://accounts.example.test",
        "is_identity_admin": False,
    }
    from app.identity import create_session_token

    client = TestClient(app)
    client.cookies.set("pdfhub_session", create_session_token(identity))
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == principal_name_for_identity(identity)
    assert payload["name"].startswith("oidc:")
    assert payload["display_name"] == "Teacher"
    assert payload["auth_source"] == "oidc"
    assert payload["scopes"] == ["files:read"]


def test_logout_clears_session_cookie():
    client = TestClient(app)
    response = client.post("/api/v1/auth/logout")
    assert response.status_code == 204
    assert "pdfhub_session=" in response.headers.get("set-cookie", "")
