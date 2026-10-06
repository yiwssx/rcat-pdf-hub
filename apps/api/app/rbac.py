from collections.abc import Iterable

ROLE_VIEWER = "viewer"
ROLE_OPERATOR = "operator"
ROLE_ADMIN = "admin"
HUMAN_ROLES = (ROLE_VIEWER, ROLE_OPERATOR, ROLE_ADMIN)
ROLE_PRECEDENCE = (ROLE_ADMIN, ROLE_OPERATOR, ROLE_VIEWER)

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


def role_for_groups(groups: Iterable[str], role_groups: dict[str, set[str]]) -> str:
    normalized_groups = {str(group).strip().casefold() for group in groups if str(group).strip()}
    for role in ROLE_PRECEDENCE:
        configured = {str(group).strip().casefold() for group in role_groups.get(role, set()) if str(group).strip()}
        if normalized_groups & configured:
            return role
    raise ValueError("Authenticated identity has no mapped PDF Hub role")
