import pytest

from app import identity
from app.principal_id import principal_name_for_identity


def test_local_admin_authentication_and_session(monkeypatch):
    monkeypatch.setattr(identity.settings, "local_auth_enabled", True)
    monkeypatch.setattr(identity.settings, "local_admin_username", "admin")
    monkeypatch.setattr(identity.settings, "local_admin_password", "correct-horse-battery-staple")

    local = identity.authenticate_local("admin", "correct-horse-battery-staple")

    assert local["subject"] == "admin"
    assert local["display_name"] == "Local Admin"
    assert local["source"] == "local"
    assert local["scopes"] == ["*"]
    assert local["is_identity_admin"] is True
    assert principal_name_for_identity(local).startswith("identity:")

    token = identity.create_session_token(local)
    restored = identity.decode_session_token(token)
    assert restored["subject"] == "admin"
    assert restored["source"] == "local"
    assert restored["scopes"] == ["*"]
    assert restored["is_identity_admin"] is True


def test_local_admin_rejects_wrong_credentials(monkeypatch):
    monkeypatch.setattr(identity.settings, "local_auth_enabled", True)
    monkeypatch.setattr(identity.settings, "local_admin_username", "admin")
    monkeypatch.setattr(identity.settings, "local_admin_password", "correct-horse-battery-staple")

    with pytest.raises(ValueError, match="Invalid local credentials"):
        identity.authenticate_local("admin", "wrong-password")

    with pytest.raises(ValueError, match="Invalid local credentials"):
        identity.authenticate_local("other-user", "correct-horse-battery-staple")


def test_local_auth_is_not_advertised_when_disabled(monkeypatch):
    monkeypatch.setattr(identity.settings, "local_auth_enabled", False)
    assert identity.public_auth_config()["local"]["enabled"] is False

    with pytest.raises(ValueError, match="disabled"):
        identity.authenticate_local("admin", "anything")
