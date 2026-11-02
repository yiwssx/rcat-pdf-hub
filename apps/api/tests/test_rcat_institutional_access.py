"""RCAT-only pilot: verified institutional OIDC and no non-member bypasses.

The mode defaults OFF for existing environments. These tests enable it only
within monkeypatch isolation and must never require a live identity provider.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
import jwt
from fastapi import HTTPException
from pydantic import ValidationError

from app.config import Settings, get_settings
from app.identity import (
    _verified_rcat_email, create_session_token, decode_session_token,
    identity_from_claims, public_auth_config, create_local_admin_identity,
)
from app.security import _identity_principal, _service_principal
from app.routers.files import create_signed_download, signed_download_file


def _institutional_mode(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "rcat_institutional_only", True)
    return settings


def _oidc_claims(email="teacher@rcat.ac.th", verified=True):
    return {
        "iss": "https://idp.example.invalid",
        "sub": "unique-idp-user-42",
        "email": email,
        "email_verified": verified,
        "groups": ["pdfhub-users"],
        "preferred_username": "teacher",
    }


def test_legacy_deployments_stay_unmodified_by_default():
    assert Settings().rcat_institutional_only is False


@pytest.mark.parametrize("overrides", [
    {"oidc_enabled": False},
    {"oidc_enabled": True, "session_cookie_secure": False},
    {"oidc_enabled": True, "ldap_enabled": True},
    {"oidc_enabled": True, "oidc_issuer": ""},
])
def test_institutional_mode_refuses_incomplete_or_unsafe_config(overrides):
    cfg = {
        "rcat_institutional_only": True,
        "oidc_enabled": True,
        "oidc_issuer": "https://idp.example.invalid",
        "oidc_client_id": "rcat-pdf",
        "session_cookie_secure": True,
    }
    cfg.update(overrides)
    with pytest.raises(ValidationError):
        Settings(**cfg)


def test_institutional_mode_disables_local_admin_and_web_console(monkeypatch):
    settings = _institutional_mode(monkeypatch)
    monkeypatch.setattr(settings, "oidc_enabled", True)
    monkeypatch.setattr(settings, "local_admin_password_hash", "non-empty-hash")
    monkeypatch.setattr(settings, "web_console_auto_login", True)
    assert not settings.local_admin_enabled
    assert not settings.web_console_auto_login_enabled
    config = public_auth_config()
    assert config["local_admin"]["enabled"] is False
    assert config["web_console"]["auto_login"] is False


@pytest.mark.parametrize("email,verified", [
    ("user@gmail.com", True),
    ("user@rcat.ac.th.evil.test", True),
    ("user@sub.rcat.ac.th", True),
    ("user@notrcat.ac.th", True),
    ("user@rcat.ac.th ", True),
    ("user@rcat.ac.th\n", True),
    (" user@rcat.ac.th", True),
    ("user＠rcat.ac.th", True),
    ("user@rcat.ac.th", False),
    ("user@rcat.ac.th", None),
    ("user@rcat.ac.th", "true"),
    ("", True),
])
def test_rcat_email_must_be_exact_and_idp_verified(email, verified):
    with pytest.raises(ValueError):
        _verified_rcat_email(email, verified)


def test_institutional_verified_oidc_login_and_cookie_round_trip(monkeypatch):
    _institutional_mode(monkeypatch)
    identity = identity_from_claims(_oidc_claims("Teacher@RCAT.AC.TH"), "oidc")
    assert identity["email"] == "teacher@rcat.ac.th"
    assert identity["email_verified"] is True
    token = create_session_token(identity)
    restored = decode_session_token(token)
    assert restored["email"] == "teacher@rcat.ac.th"
    assert restored["email_verified"] is True
    assert restored["roles"] == ["operator"]
    assert restored["source"] == "oidc"


@pytest.mark.parametrize("bad_claims", [
    {"email": "teacher@gmail.com"},
    {"email": "teacher@rcat.ac.th", "email_verified": False},
    {"email": "teacher@rcat.ac.th", "email_verified": None},
])
def test_institutional_oidc_denies_bad_claims(monkeypatch, bad_claims):
    _institutional_mode(monkeypatch)
    claims = {**_oidc_claims(), **bad_claims}
    with pytest.raises(ValueError):
        identity_from_claims(claims, "oidc")


def test_institutional_mode_blocks_ldap_even_with_institutional_mail(monkeypatch):
    _institutional_mode(monkeypatch)
    with pytest.raises(ValueError):
        identity_from_claims(_oidc_claims(), "ldap")


def test_preexisting_session_without_email_is_invalid_when_mode_enabled(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "rcat_institutional_only", False)
    identity = identity_from_claims(
        {"sub": "42", "groups": ["pdfhub-users"]}, "oidc",
    )
    old_token = create_session_token(identity)
    monkeypatch.setattr(settings, "rcat_institutional_only", True)
    with pytest.raises(jwt.InvalidTokenError):
        decode_session_token(old_token)


def test_old_non_oidc_sessions_and_service_keys_cannot_bypass(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "rcat_institutional_only", False)
    token = create_session_token(create_local_admin_identity("admin"))
    monkeypatch.setattr(settings, "rcat_institutional_only", True)
    with pytest.raises(jwt.InvalidTokenError):
        decode_session_token(token)
    with pytest.raises(HTTPException) as exc:
        _service_principal("any-service-token", SimpleNamespace())
    assert exc.value.status_code == 403
    with pytest.raises(HTTPException) as denied:
        _identity_principal({
            "name": "local-admin:admin", "source": "local-admin",
            "roles": ["admin"], "scopes": ["*"],
        })
    assert denied.value.status_code == 403


def test_anonymous_signed_link_minting_and_old_links_are_disabled(monkeypatch):
    _institutional_mode(monkeypatch)
    with pytest.raises(HTTPException) as minted:
        create_signed_download(
            "file1", ttl_seconds=60,
            principal=SimpleNamespace(name="user:teacher@rcat.ac.th"),
            db=SimpleNamespace(),
        )
    assert minted.value.status_code == 403
    with pytest.raises(HTTPException) as used:
        signed_download_file(
            "file1", expires=9999999999,
            token="a" * 64, db=SimpleNamespace(),
        )
    assert used.value.status_code == 403



def test_google_oidc_without_workspace_groups_allows_verified_school_users(monkeypatch):
    """Google standard ID tokens have no Workspace group claims."""
    _institutional_mode(monkeypatch)
    settings = get_settings()
    monkeypatch.setattr(settings, "rcat_admin_emails", "")
    shared_display = "Teacher"
    first = identity_from_claims(
        {**_oidc_claims("first@rcat.ac.th"), "groups": [], "preferred_username": shared_display},
        "oidc",
    )
    second = identity_from_claims(
        {**_oidc_claims("second@rcat.ac.th"), "groups": [], "preferred_username": shared_display},
        "oidc",
    )
    assert first["roles"] == second["roles"] == ["operator"]
    assert "pdf:convert" in first["scopes"]
    assert first["name"] == "user:first@rcat.ac.th"
    assert second["name"] == "user:second@rcat.ac.th"
    assert decode_session_token(create_session_token(first))["roles"] == ["operator"]


def test_oidc_explicit_viewer_group_stays_read_only(monkeypatch):
    _institutional_mode(monkeypatch)
    identity = identity_from_claims(
        {**_oidc_claims(), "groups": ["pdfhub-viewers"]}, "oidc",
    )
    assert identity["roles"] == ["viewer"]
    assert "files:read" in identity["scopes"]
    assert "pdf:convert" not in identity["scopes"]


def test_rcat_admin_email_allowlist_is_exact_and_revocable(monkeypatch):
    settings = _institutional_mode(monkeypatch)
    monkeypatch.setattr(settings, "rcat_admin_emails", "admin@rcat.ac.th")
    admin = identity_from_claims(
        {**_oidc_claims("ADMIN@RCAT.AC.TH"), "groups": []}, "oidc",
    )
    other = identity_from_claims(
        {**_oidc_claims("admin2@rcat.ac.th"), "groups": []}, "oidc",
    )
    assert admin["roles"] == ["admin"]
    assert admin["scopes"] == ["*"]
    assert other["roles"] == ["operator"]
    signed = create_session_token(admin)
    monkeypatch.setattr(settings, "rcat_admin_emails", "")
    revoked = decode_session_token(signed)
    assert revoked["roles"] == ["operator"]
    assert "*" not in revoked["scopes"]


@pytest.mark.parametrize("bad", [
    "administrator@gmail.com",
    "admin@sub.rcat.ac.th",
    "admin@rcat.ac.th.evil.example",
    "admin@rcat.ac.th,other@gmail.com",
])
def test_invalid_rcat_admin_email_configuration_fails_closed(bad):
    with pytest.raises(ValidationError):
        Settings(rcat_admin_emails=bad)



def test_long_verified_rcat_email_has_stable_bounded_owner(monkeypatch):
    _institutional_mode(monkeypatch)
    email = "a" * 116 + "@rcat.ac.th"
    identity = identity_from_claims(
        {**_oidc_claims(email), "groups": []}, "oidc",
    )
    assert identity["email"] == email
    assert identity["name"].startswith("user:sha256:")
    assert len(identity["name"]) <= 120
    assert decode_session_token(create_session_token(identity))["name"] == identity["name"]


def test_old_oidc_cookie_cannot_retain_display_name_as_owner(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "rcat_institutional_only", False)
    old = identity_from_claims(_oidc_claims(), "oidc")
    assert old["name"] == "user:teacher"
    cookie = create_session_token(old)
    monkeypatch.setattr(settings, "rcat_institutional_only", True)
    assert decode_session_token(cookie)["name"] == "user:teacher@rcat.ac.th"


@pytest.mark.parametrize("return_to,expected", [
    ("//evil.invalid/path", "/"),
    (r"/\evil.invalid/path", "/"),
    (r"/safe\evil", "/"),
    ("https://evil.invalid", "/"),
    ("/safe?next=/documents", "/safe?next=/documents"),
    ("/safe\r\nLocation: https://evil.invalid", "/"),
])
def test_oidc_redirect_rejects_external_browser_backslash_urls(return_to, expected):
    from app.identity import _safe_return_to
    assert _safe_return_to(return_to) == expected
