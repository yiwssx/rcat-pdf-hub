# P7F.2 — Job Permissions & Action Review

Status: **IN PROGRESS — OWNERSHIP HARDENING**. This matrix records implemented authorization and what remains to be reviewed before enabling Admin cross-account mutations.

| Principal | Generic job list/detail | Generic cancel/retry/terminal-clear | Admin triage GET | Cross-account Admin action |
| --- | --- | --- | --- | --- |
| Anonymous | 401 | 401 | 401 | Not implemented |
| Human Viewer (viewer) | Own jobs with `jobs:read` | Denied without `jobs:manage` | 403 | Not implemented |
| Human Operator (operator) | Own jobs with `jobs:read` | Own jobs only, when `jobs:manage` and state permit | 403 | Not implemented |
| Human Admin (OIDC / LDAP / local-admin) | **Own jobs only**, even with wildcard `*` | **Own jobs only**, state and operation checks remain | Read-only, audited and minimized | **Not implemented** |
| Legacy signed session with wildcard | **Own jobs only** | **Own jobs only**, existing scopes still apply | 403 | Not implemented |
| Service API key | Own jobs based on explicit scopes | Own jobs with approved scopes | 403, including wildcard service keys | Not implemented |
| Bootstrap API key | Existing privileged service-wide behavior preserved for backward compatibility | Existing privileged behavior preserved | 403, including wildcard | Not implemented |

## Verified safeguards

- `GET /api/v1/admin/jobs/triage` is **not** interchangeable with `GET /api/v1/jobs`. It returns only ID, operation, state, progress, timestamps and generic failure presence; it has validated filters, bounded paging and mandatory fail-closed audit.
- Signed identity/session authorization must never infer data ownership bypass merely from wildcard `*`. Generic job detail, list, cancel/retry and terminal-history deletion remain owner-scoped for all identities.
- Service and bootstrap credentials are excluded from the dedicated human Admin triage endpoint. Existing bootstrap API compatibility is retained until a separate review; do not expand its UI exposure.
- Existing operation-state preconditions and backend scope checks remain in force. A client confirmation dialog is **not** an authorization mechanism.

## Work still required to close 7F.2

1. Decide which cross-account Admin actions are permissible and which should be prohibited. A retry can affect file ownership, quota attribution and job requester identity; it must not silently reassign a user's job to Admin.
2. Where approved, use dedicated POST endpoints with server-side human-Admin enforcement, expected-state concurrency checks, explicit confirmation context, audit of both intent and outcome, and safe errors.
3. Generic repair is not supported by existing jobs endpoints and must **not** be represented as an available action. Reconciliation/repair belongs to separately reviewed storage workflows.
4. Add negative role, ownership, concurrency, job lifecycle and audit-failure tests. Require Core API contract/coverage, Web Playwright, CodeQL and Dependency Review on the final commit.

No production deploy or Phase 7 release is authorized by this file.
