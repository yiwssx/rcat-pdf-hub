from collections.abc import Iterable

ROLE_VIEWER = "viewer"
ROLE_OPERATOR = "operator"
ROLE_ADMIN = "admin"
HUMAN_ROLES = (ROLE_VIEWER, ROLE_OPERATOR, ROLE_ADMIN)

VIEWER_SCOPES = frozenset({"files:read", "jobs:read"})


def normalize_roles(values: Iterable[str]) -> tuple[str, ...]:
    requested = {str(value).strip().lower() for value in values if str(value).strip()}
    unknown = requested - set(HUMAN_ROLES)
    if unknown:
        raise ValueError(f"Unknown human role(s): {', '.join(sorted(unknown))}")
    return tuple(role for role in HUMAN_ROLES if role in requested)


def scopes_for_roles(roles: Iterable[str], operator_scopes: Iterable[str]) -> set[str]:
    normalized = set(normalize_roles(roles))
    if ROLE_ADMIN in normalized:
        return {"*"}

    scopes: set[str] = set()
    if ROLE_VIEWER in normalized:
        scopes.update(VIEWER_SCOPES)
    if ROLE_OPERATOR in normalized:
        scopes.update(str(scope).strip() for scope in operator_scopes if str(scope).strip())
    return scopes


def is_admin_role(roles: Iterable[str]) -> bool:
    return ROLE_ADMIN in set(normalize_roles(roles))
