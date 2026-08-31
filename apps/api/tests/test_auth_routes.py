from fastapi.testclient import TestClient

from app import identity, security
from app.main import app
from app.principal_id import principal_name_for_identity
from app.routers import auth


def test_auth_config_is_public():
    client = TestClient(app)
    response = client.get("/api/v1/auth/config")
    assert response.status_code == 200
    payload = response.json()
    assert payload["api_key"]["enabled"] is True
    assert "local" in payload
    assert "oidc" in payload
    assert "ldap" in payload


def test_local_login_route_sets_human_session(monkeypatch):
    for module in (identity, auth):
        monkeypatch.setattr(module.settings, "local_auth_enabled", True)
        monkeypatch.setattr(module.settings, "local_admin_username", "admin")
        monkeypatch.setattr(module.settings, "local_admin_password", "local-route-password-123")
    monkeypatch.setattr(security, "ensure_rate_limit", lambda *args, **kwargs: None)

    client = TestClient(app)
    response = client.post(
        "/api/v1/auth/local/login",
        json={"username": "admin", "password": "local-route-password-123"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["display_name"] == "Local Admin"
    assert payload["auth_source"] == "local"
    assert payload["is_admin"] is True
    assert payload["name"].startswith("identity:")
    assert "pdfhub_session=" in response.headers.get("set-cookie", "")

    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["auth_source"] == "local"
    assert me.json()["is_admin"] is True


def test_cookie_session_authentication_uses_stable_oidc_principal(monkeypatch):
    monkeypatch.setattr(security, "ensure_rate_limit", lambda *args, **kwargs: None)
    identity_data = {
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
    client.cookies.set("pdfhub_session", create_session_token(identity_data))
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == principal_name_for_identity(identity_data)
    assert payload["name"].startswith("oidc:")
    assert payload["display_name"] == "Teacher"
    assert payload["auth_source"] == "oidc"
    assert payload["scopes"] == ["files:read"]


def test_logout_clears_session_cookie():
    client = TestClient(app)
    response = client.post("/api/v1/auth/logout")
    assert response.status_code == 204
    assert "pdfhub_session=" in response.headers.get("set-cookie", "")
