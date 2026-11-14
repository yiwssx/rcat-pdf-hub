"""Opt-in, subject-bound Google Workspace RBAC with a one-time owner bootstrap.

Only a provider-verified institutional OIDC identity may receive a database role.
The initial Super Admin email is an explicit operator-configured exact match,
never a first-login-wins rule. Bootstrap is permanently marked by immutable sub.
"""
from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.audit import audit_event
from app.config import get_settings
from app.identity import _institutional_owner_name, _require_google_workspace, _verified_rcat_email
from app.models import InstitutionalBootstrapClaim, InstitutionalRoleAssignment
from app.rbac import ROLE_ADMIN, ROLE_OPERATOR, ROLE_SUPER_ADMIN, is_admin_role, scopes_for_roles

settings = get_settings()
BOOTSTRAP_KEY = "institutional-super-admin"


def _authenticated_owner(identity: dict) -> tuple[str, str]:
    if identity.get("source") not in {"oidc", "oidc-bearer"}:
        raise HTTPException(status_code=403, detail="Verified institutional OIDC required")
    try:
        email = _verified_rcat_email(identity.get("email"), identity.get("email_verified"))
        _require_google_workspace(identity.get("hosted_domain"))
        owner = _institutional_owner_name(str(identity.get("subject") or ""))
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="Verified institutional identity required") from exc
    if identity.get("name") != owner:
        raise HTTPException(status_code=403, detail="Institutional subject mismatch")
    return email, owner


def resolve_institutional_identity(db: Session, identity: dict) -> dict:
    """Re-evaluate stored roles and revocations on every authenticated request.

    No raw email claim, API key, local admin or stale cookie can assign a role.
    A pending email assignment is bound once to the verified issuer-scoped sub.
    """
    if not settings.rcat_role_registry_enabled or not settings.rcat_institutional_only:
        return identity
    email, owner = _authenticated_owner(identity)
    record = db.scalar(select(InstitutionalRoleAssignment).where(
        InstitutionalRoleAssignment.owner_name == owner
    ))
    if record is None:
        record = db.scalar(select(InstitutionalRoleAssignment).where(
            InstitutionalRoleAssignment.email == email
        ))
        if record is not None and record.owner_name not in (None, owner):
            # Never silently transfer a role when a Workspace email is reused.
            raise HTTPException(status_code=403, detail="Institutional email is bound to another subject")

    claim = db.get(InstitutionalBootstrapClaim, BOOTSTRAP_KEY)
    approved_email = settings.rcat_bootstrap_super_admin_email
    first_owner = bool(approved_email and email == approved_email and claim is None)
    if first_owner and not audit_event(
        "rbac.bootstrap_requested", owner, "institutional_role", owner,
        {"role": ROLE_SUPER_ADMIN},
    ):
        raise HTTPException(status_code=503, detail="Role audit unavailable")

    changed = False
    if record is None:
        # Retain legacy trusted admin group/email mapping during opt-in migration.
        legacy_role = ROLE_ADMIN if ROLE_ADMIN in identity.get("roles", ()) else ROLE_OPERATOR
        record = InstitutionalRoleAssignment(
            email=email, owner_name=owner,
            role=ROLE_SUPER_ADMIN if first_owner else legacy_role,
            active=True, granted_by="bootstrap" if first_owner else "existing-oidc-policy",
        )
        db.add(record)
        changed = True
    elif record.owner_name is None:
        record.owner_name = owner
        changed = True
    if first_owner:
        record.role = ROLE_SUPER_ADMIN
        record.active = True
        db.add(InstitutionalBootstrapClaim(
            key=BOOTSTRAP_KEY, owner_name=owner, email=email,
        ))
        changed = True
    if changed:
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            # Fail closed on concurrent bootstrap/binding; retry next request.
            raise HTTPException(status_code=409, detail="Concurrent role assignment; retry") from exc

    if not record.active:
        raise HTTPException(status_code=403, detail="Institutional account is disabled")

    role = record.role
    if role not in {"viewer", "operator", "admin", "super_admin"}:
        raise HTTPException(status_code=403, detail="Institutional role invalid")

    resolved = dict(identity)
    resolved["roles"] = [role]
    resolved["scopes"] = sorted(scopes_for_roles((role,), settings.human_scope_set))
    resolved["is_identity_admin"] = is_admin_role((role,))
    return resolved


def require_super_admin(principal) -> None:
    """A privileged wildcard alone cannot manage human role assignments."""
    if (not settings.rcat_institutional_only
            or not settings.rcat_role_registry_enabled
            or principal.auth_source not in {"oidc", "oidc-bearer"}
            or ROLE_SUPER_ADMIN not in principal.roles
            or not principal.is_identity_admin):
        raise HTTPException(status_code=403, detail="Institutional Super Admin required")
