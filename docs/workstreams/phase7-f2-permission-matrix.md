# P7F.2 — Job Permissions & Action Review

Status: **COMPLETE WITH OWNER-ONLY SECURITY BOUNDARY**. Human Admin cross-account job actions are deliberately not authorized in P7; this matrix records the reviewed, supported owner-scoped operations.

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

## Owner-scoped action safeguards (implementation in progress)

- Existing job Cancel, Retry and terminal-history deletion now require an `audit_event` intent record **before** queue/state mutation. If Audit persistence fails, the endpoint responds HTTP 503 and does not perform the action.
- Job detail asks explicit confirmation before Cancel or Retry; declining means no request is sent. A synchronous in-flight guard prevents double-activation before React re-renders.
- Existing outcome audit entries still follow successful execution. If the outcome Audit fails after a queue mutation, the prior intent entry preserves an accountable trail, but post-action audit availability must still be monitored operationally.
- These controls apply only to jobs the current signed identity owns. Admin triage remains read-only and does not expose cross-account action buttons.

## Scope decision and future extension

The P7F.2 acceptance scope is **owner-only** for Cancel, Retry and terminal-history cleanup. Its permission matrix, existing action preconditions, client confirmation and persisted preaction audit are implemented and tested in PRs #143–#144. Cross-account Admin mutations are **not supported** in Phase 7, not waiting to become enabled silently. Any future change requires its own proposal, access review, concurrency and quota-attribution tests, failure audit handling and release approval. General file/job repair is not supported.

No production deploy or release is authorized by this security decision.
