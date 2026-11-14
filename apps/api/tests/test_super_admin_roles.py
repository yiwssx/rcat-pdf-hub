"""One-time institutional Super Admin, subject binding, revocation, role API gates."""
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.config import get_settings
from app.db import Base
from app.identity import create_session_token, decode_session_token, identity_from_claims
from app.models import InstitutionalBootstrapClaim, InstitutionalRoleAssignment
from app.role_registry import resolve_institutional_identity, require_super_admin
from app.routers.admin import (
    InstitutionalRoleUpdate,
    disable_institutional_role,
    grant_institutional_role,
    list_institutional_roles,
)
from app.security import _identity_principal


@pytest.fixture
def scenario(monkeypatch):
    settings = get_settings()
    for key, value in (
        ("rcat_institutional_only", True),
        ("rcat_role_registry_enabled", True),
        ("rcat_bootstrap_super_admin_email", "owner@rcat.ac.th"),
        ("oidc_issuer", "https://accounts.google.com"),
        ("rcat_admin_emails", ""),
    ):
        monkeypatch.setattr(settings, key, value)
    monkeypatch.setattr("app.role_registry.audit_event", lambda *a, **kw: True)
    monkeypatch.setattr("app.routers.admin.audit_event", lambda *a, **kw: True)
    monkeypatch.setattr("app.security.ensure_rate_limit", lambda *a, **kw: None)
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        yield db
    engine.dispose()


def _person(email: str, sub: str):
    return identity_from_claims({
        "sub": sub, "email": email, "email_verified": True, "hd": "rcat.ac.th",
    }, "oidc")


def _principal(db, email="owner@rcat.ac.th", sub="first-person"):
    return _identity_principal(_person(email, sub), db)


def test_explicit_bootstrap_only_and_immutable_subject(scenario):
    normal = _principal(scenario, "user@rcat.ac.th", "user-sub")
    assert normal.roles == {"operator"}
    assert not normal.is_identity_admin
    with pytest.raises(HTTPException):
        require_super_admin(normal)
    owner = _principal(scenario)
    assert owner.roles == {"super_admin"}
    assert owner.is_identity_admin and owner.scopes == {"*"}
    require_super_admin(owner)
    marker = scenario.get(InstitutionalBootstrapClaim, "institutional-super-admin")
    assert marker.owner_name == owner.name
    # Recycled verified email has a different Google sub: cannot inherit role.
    with pytest.raises(HTTPException) as stolen:
        _principal(scenario, "owner@rcat.ac.th", "different-google-sub")
    assert stolen.value.status_code == 403
    assert _principal(scenario).roles == {"super_admin"}


def test_role_registry_disabled_has_no_upgrade_or_database_side_effects(scenario, monkeypatch):
    monkeypatch.setattr(get_settings(), "rcat_role_registry_enabled", False)
    owner = _principal(scenario)
    assert owner.roles == {"operator"}
    assert scenario.get(InstitutionalBootstrapClaim, "institutional-super-admin") is None


def test_admin_assignment_pending_bind_revocation_and_stale_cookie(scenario):
    owner = _principal(scenario)
    pending = grant_institutional_role(
        "admin@rcat.ac.th", InstitutionalRoleUpdate(role="admin"),
        principal=owner, db=scenario,
    )
    assert pending["role"] == "admin" and not pending["linked"]
    admin_identity = _person("admin@rcat.ac.th", "verified-admin-sub")
    cookie = create_session_token(admin_identity)
    admin = _identity_principal(decode_session_token(cookie), scenario)
    assert admin.roles == {"admin"}
    assert admin.is_identity_admin
    assert list_institutional_roles(principal=owner, db=scenario)
    with pytest.raises(HTTPException) as denied:
        grant_institutional_role(
            "somebody@rcat.ac.th", InstitutionalRoleUpdate(role="super_admin"),
            principal=admin, db=scenario,
        )
    assert denied.value.status_code == 403
    grant_institutional_role(
        "admin@rcat.ac.th", InstitutionalRoleUpdate(role="viewer"),
        principal=owner, db=scenario,
    )
    # Prior admin cookie is re-evaluated from DB on every request.
    reduced = _identity_principal(decode_session_token(cookie), scenario)
    assert reduced.roles == {"viewer"} and "*" not in reduced.scopes
    disable_institutional_role("admin@rcat.ac.th", principal=owner, db=scenario)
    with pytest.raises(HTTPException) as revoked:
        _identity_principal(decode_session_token(cookie), scenario)
    assert revoked.value.status_code == 403


def test_prevent_self_demote_and_unlinked_super_admin_invitation(scenario):
    owner = _principal(scenario)
    with pytest.raises(HTTPException) as same:
        grant_institutional_role(
            "owner@rcat.ac.th", InstitutionalRoleUpdate(role="viewer"),
            principal=owner, db=scenario,
        )
    assert same.value.status_code == 403
    with pytest.raises(HTTPException) as self_disable:
        disable_institutional_role("owner@rcat.ac.th", principal=owner, db=scenario)
    assert self_disable.value.status_code == 403
    with pytest.raises(HTTPException) as unlinked:
        grant_institutional_role(
            "new@rcat.ac.th", InstitutionalRoleUpdate(role="super_admin"),
            principal=owner, db=scenario,
        )
    assert unlinked.value.status_code == 409


def test_bootstrap_not_promoted_if_audit_is_unavailable(scenario, monkeypatch):
    monkeypatch.setattr("app.role_registry.audit_event", lambda *a, **kw: False)
    with pytest.raises(HTTPException) as error:
        _principal(scenario)
    assert error.value.status_code == 503
    assert scenario.get(InstitutionalBootstrapClaim, "institutional-super-admin") is None
    assert scenario.scalar(select(InstitutionalRoleAssignment)) is None


def test_role_api_rejects_lookalike_email(scenario):
    owner = _principal(scenario)
    with pytest.raises(HTTPException) as bad:
        grant_institutional_role(
            "bad@rcat.ac.th.evil.org", InstitutionalRoleUpdate(role="admin"),
            principal=owner, db=scenario,
        )
    assert bad.value.status_code == 422
