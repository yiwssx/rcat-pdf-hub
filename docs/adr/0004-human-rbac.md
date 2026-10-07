# ADR-0004: Model human authorization with explicit roles

- Status: Accepted
- Date: 2026-10-06

## Context

Human authentication already produced scope-bearing identities, but authorization policy was implicit: an identity in a configured admin group received wildcard scope and every other human identity received one shared scope set. That made the effective role impossible to inspect directly and made later group mapping dependent on identity-provider-specific conditionals.

## Decision

Define three human roles in `app.rbac`:

- `viewer`: read-only file and job visibility;
- `operator`: the configured human document-workflow scopes;
- `admin`: wildcard administrative access.

Role-to-scope expansion is centralized in the RBAC module. Human session tokens carry role names, and decoded human sessions recompute effective scopes from the role matrix instead of trusting a serialized scope list. The anonymous/private-network Web Console bootstrap is an `operator`; Local Admin is an `admin`.

Service API keys remain scope-based machine identities and are not converted to human roles.

OIDC/LDAP groups select these roles through explicit fail-closed mappings. Identities without a recognized configured role group are rejected, and institutional sessions are remapped from current groups on decode so stale privilege is not retained.

## Consequences

- Human role semantics have one source of truth.
- `/api/v1/auth/me` can expose roles separately from effective scopes.
- Existing human scope configuration remains the operator-role scope set.
- Service integrations keep their existing API-key scope model.
- Session authorization can be tightened centrally without changing every route.
- The Admin Console exposes effective identity, role, groups and resolved scopes for troubleshooting without exposing credentials.

## Validation

Backend tests must cover the role permission matrix, admin wildcard behavior, role-bearing session round trips, and role visibility in authentication responses.
