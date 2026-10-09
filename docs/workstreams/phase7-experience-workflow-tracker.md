# Phase 7 — Experience & Workflow Master Tracker

Status: **IN PROGRESS — P7B.1 TASK JOURNEY**

Default branch: `main`  
Pre-planning code baseline: `4f808fd3d8e094e1d37b361ff171a021f5e02ace` (2026-10-09)  
Prior release: `v0.6.0` — Phase 6 **COMPLETE**, tag unchanged  
Phase 7 target version: **TBD at release planning**  
Tracker role: **canonical source of truth for Phase 7 execution status**

Source of scope: [PHASE7.md](../../PHASE7.md). Decision to validate in P7A: [ADR-0005](../adr/0005-task-first-journey.md) (Proposed).

## Starting point (source-backed)

| Present behavior | Phase 7 problem |
| --- | --- |
| `PdfHubApp` renders Home, Document Workspace, Files or Admin based on initial view and selected file | Deep-link tool intent must be explicit; do not let a preselected file silently override the URL |
| `chooseTool` may select a compatible existing file and click hidden `#files` upload | Offer explicit visible upload/library intake and confirmation of selected files |
| `ToolWorkspace` owns per-tool settings and job payloads | Reuse this seam (ADR-0001), rather than duplicating per-tool flow engines |
| `submit` creates a job and opens `JobDrawer` | Need durable job/progress/result steps, back/refresh recovery and immediate download |
| `/files` supports server-side search, filter, pagination, retention and deletion | Preserve file-first workflow; allow bidirectional tool/result handoff |
| `/admin` combines diagnostics with keys, quotas, webhook DLQ and audit | Give Admin operations task-focused navigation and scoped actions |
| Existing Jobs API/`output_file_id`, RQ queues, RBAC and storage reconciliation | Reuse; do not invent a new backend workflow service or cross-user permissions |

## Task register

Each row has one deliverable, a verification obligation, an owner/PR evidence placeholder and a status. Never mark complete on code presence alone; link the merged PR and the applicable CI/test runs.

| ID | Deliverable / work package | Status | Dependencies | Evidence |
| --- | --- | --- | --- | --- |
| 7.0 | Planning: PHASE7, canonical Master Tracker, proposed ADR-0005, glossary and routing/policy guard | COMPLETE | Phase 6 baseline | PR #128 (planning-only) |
| 7A.1 | Stable tool catalog and `/tools/[slug]` navigation; invalid slug, direct URL, back/forward/refresh | COMPLETE | 7.0 | PR #129 merged to `main` as `cf266d25d26bae9af450ece58f4fd1b374afaa08`; Web CI #37894340265, CodeQL #37894340305, Dependency Review #37894340179 PASS |
| 7A.2 | Tool-first file intake: upload/My Files, type/count validation, explicit selection and merge ordering | COMPLETE | 7A.1 | PR #130 merged `8da9bb618bbbeeed10a1a4a043426bdc75153b83`; Web CI #37895142089, CodeQL #37895142051, Dependency Review #37895142092 PASS |
| 7B.1 | Unified client journey state transitions, back/cancel, duplicate-submit guard, per-tool capability metadata | IN PROGRESS | 7A.2 | `feat/p7b1-client-journey-states`; PR and CI pending |
| 7B.2 | Configure/preview/submit contract using current ToolWorkspace and one primary action | PENDING | 7B.1 | — |
| 7C.1 | Job detail/progress surface for queued/running/completed/failed/cancelled; polling and error recovery | PENDING | 7B.2 | — |
| 7C.2 | Durable authenticated result route; correct output/expiry handling; primary download action | PENDING | 7C.1 | — |
| 7C.3 | Continue with eligible tool via `output_file_id` without downloading/reuploading | PENDING | 7C.2 | — |
| 7D.1 | User-scoped My Jobs history/status filtering; reopen active or prior jobs | PENDING | 7C.2 | — |
| 7D.2 | My Files ↔ tools ↔ result navigation; refresh recovery and expired/missing file states | PENDING | 7D.1 | — |
| 7E.1 | Admin information architecture: Overview, Jobs, Access, Storage, Diagnostics, Integrations | PENDING | 7.0 | — |
| 7E.2 | Actionable Admin Overview based on existing availability, jobs, queue and storage status | PENDING | 7E.1 | — |
| 7F.1 | Read-only Admin job triage by queue/status/failure; scoped diagnostics, bounded queries | PENDING | 7E.2 | — |
| 7F.2 | Reviewed permission matrix and audited retry/cancel/repair operations where supported | PENDING | 7F.1 | — |
| 7G.1 | Human effective-role/quotas workflows; new identity mutations only after explicit security review | PENDING | 7E.1 | — |
| 7G.2 | Storage/retention/reconciliation, service keys, webhooks and integration operations with safe confirmations | PENDING | 7E.2, 7F.2 | — |
| 7H.1 | User/Admin E2E journeys, denial tests, mobile/a11y/performance and backend regression gates | PENDING | 7A–7G | — |
| 7H.2 | Documentation, staged rollout/rollback, production verification and release gate (version TBD) | PENDING | 7H.1 | — |

**Roll-up:** P7A `COMPLETE` (7A.1 and 7A.2 merged); P7B `IN PROGRESS` (7B.1 active); P7C, P7D, P7E, P7F, P7G and P7H `PENDING`. P7A completion is not a Phase 7 release.

## User flow contract

### Task-first (primary)

`Tool catalog → tool-specific route → select/upload inputs → configure/preview → submit → job state → result/download/continue`.

- A tool can open without files. User sees separate actions for Upload and Choose from My Files.
- Never silently substitute unrelated existing files. The selected file IDs/order shown must match the submission payload.
- Validate MIME/type, allowed operations, quantity and size before creating a job. Merge requires at least two PDFs; image-to-PDF allows multiple supported images; signed download and archival are non-processing tools and may use a different result interaction.
- User sees backend-authoritative `queued`, `running`, `completed`, `failed` and `cancelled`. Do not show "completed" until confirmed.
- Proposed `/jobs/[id]` and `/jobs/[id]/result` route shapes must be reviewed in 7A/7C, not treated as existing routes.
- Job detail and result recover after navigation/refresh using scoped job/file reads, never an in-memory-only success toast.
- Handle upload failure, quota/permission denied, lost connection, missing/expired output, retry and cancellation, without raw sensitive errors.
- Result has primary download; compatible follow-on tools may receive an authorized `output_file_id` without another upload.

### File-first (secondary)

`/files → select owned document(s) → compatible tool → configure/submit → result → My Files/My Jobs`. Preserve server search, filter, paging, retention and deletion. Multi-selection compatibility requires design and tests; current file library is not silently converted into a full processing queue.

## Admin flow contract

`Overview → operational issue → authorized scoped details → explicit corrective action → verified outcome and audit`.

| Admin area | Existing foundation | Planned change |
| --- | --- | --- |
| Overview | API/admin status, queue depth, disk, tool readiness | Purpose-driven summaries, errors and routes to diagnosis |
| Jobs | User jobs and queue telemetry | Admin-wide job listing/action **only with new scoped read/write endpoints and audits** |
| Access | Viewer/operator/admin, service policies, OIDC/LDAP mapping | Effective-role introspection and quota workflow; identity mutations separately approved |
| Storage | File library, dry-run DB/storage reconciliation | Capacity, retention alerts, scoped reconciliation; no automatic destructive repair |
| Diagnostics | Service checks, metrics/alerts/traces | Worker/queue/job failure triage and clear operational next steps |
| Integrations | API Keys, Webhook DLQ/replay, Paperless | Separated setup/status/error-handling routes and audit |

An Admin overview is **not** permission to inspect all document contents. Review authorization, purpose, query bounds, data minimization and audit before enabling cross-user job reads or mutations.

## Execution order and acceptance

Critical path: `7.0 → 7A → 7B → 7C → 7D → 7H`. Admin path: `7.0 → 7E → 7F → 7G → 7H`. Parallelize only independent, non-conflicting PRs. A wave closes only when all its tasks and relevant public-seam regression tests pass.

| Acceptance scenario | Minimum evidence |
| --- | --- |
| Direct tool navigation | Deep links, invalid slugs, back/forward and refresh work |
| Explicit file intake | Correct type/count and visible file order/selection; payload equals selection |
| Async processing | Reproducible queued/running/succeeded/failed/cancelled transitions; no duplicate submit in normal flow |
| Result page | Authorized job and output read, download, expired/missing case and reload |
| Chaining | Completed output used by second tool with zero redundant uploads |
| My Files/My Jobs | Owned data only; paged library and retention semantics preserved |
| Admin diagnosis | Correct RBAC denial, queue/status visibility, actionable errors, audited privileged operations |
| Quality | CodeQL, Dependency Review, Web CI, Core API CI, API contract, backend coverage, Playwright/a11y and measured performance; applicable `make validate-free` and production gate |

**Experience targets:** five identifiable user-facing stages (not necessarily five clicks), zero unnecessary reupload during supported chaining, understandable recovery and resumability. Capture baseline before asserting conversion rates, percent performance improvement or latency threshold; do not fabricate metrics.

## Risks and mitigation

- **Lost UI state after refresh:** store durable result identity as job ID; rehydrate from authorized backend state. Unsaved pre-submit settings can remain ephemeral with clear discard warning.
- **Wrong file processed:** require explicit selected input review and regression assertion of submitted IDs/order.
- **Cross-user result leakage:** server ownership checks and negative tests for job/output links.
- **Stuck jobs or repeated submissions:** state-specific retry/cancel/timeout paths and duplicate-submit prevention.
- **Quota, retention and storage misuse:** preserve current enforcement and clear expired/missing states.
- **Privilege escalation:** no new global Admin endpoints until role matrix, scope checks, query bounds and audit pass.
- **Regression from routing/UX work:** staged route-level PRs, mobile/a11y/performance checks, and backward-compatibility tests.

## Working rules

1. One coherent objective per PR; update task status/evidence and this Activity Log in the **same PR**.
2. For implementation: measure/reproduce current gap, record a public-seam failing test, implement minimum behavior, run the applicable gates, review diff, merge only when green.
3. Preserve accepted ADR-0001 (ToolWorkspace settings ownership), ADR-0004 (RBAC) and the published Phase 6 `v0.6.0` tag.
4. ADR-0005 is `Proposed`: finalize route/interface details in P7A before promoting it to `Accepted`.
5. No new workflow service, backend status type, storage engine, paid cloud dependency or UI visual rewrite by default.
6. Never disable source security scanners, coverage, API-contract, a11y/performance, backup or production release gates.
7. Use file/job ownership on every result/deep link; UI route guards do not replace server authorization.
8. Admin destructive actions require distinct confirmation and durable audit. Global jobs/users endpoints require separate threat-model review.
9. No P7 release version, tag, migration, deploy or production environment mutation during planning.
10. No work is `COMPLETE` based on a passing PR alone when its acceptance criteria require operator/deployment evidence.

## Activity log

| Date | Task | Action / decision | Evidence | Result |
| --- | --- | --- | --- | --- |
| 2026-10-09 | 7.0 | Baseline identified, two user paths + admin path defined; create master tracker and proposed ADR; pause P7 implementation until requested | Pre-plan `main` `4f808fd3d8e094e1d37b361ff171a021f5e02ace`; PR #128 | PLAN READY |
| 2026-10-09 | 7A.1 | Tool deep links merged after full checks passed; 404, navigation/reload and authorized optional file query covered by Playwright | PR #129, merge `cf266d25d26bae9af450ece58f4fd1b374afaa08`; Web CI #37894340265, CodeQL #37894340305, Dependency Review #37894340179 | COMPLETE |
| 2026-10-09 | 7A.2 | Validated upload/library picker, exact merge and image order and unsupported file recovery; merged after all required checks | PR #130, merge `8da9bb618bbbeeed10a1a4a043426bdc75153b83`; Web CI #37895142089, CodeQL #37895142051, Dependency Review #37895142092 | COMPLETE |
| 2026-10-09 | 7B.1 | Add presentation-only task stages, accessible progress steps, capability metadata, synchronous duplicate-submit guard and browser regressions | `feat/p7b1-client-journey-states`; tests/CI pending | IN PROGRESS |

## Current next action

**P7A is complete and merged.** Validate P7B.1 client journey and duplicate-submit regression gates; merge with exact CI evidence, then implement P7B.2 configuration/preview/action contract. P7E Admin information architecture may proceed independently. No production deployment until P7H.

## Tracker state protocol

Allowed statuses: `PENDING`, `IN PROGRESS`, `BLOCKED`, `COMPLETE`, `SUPERSEDED`.

When continuing in a later session, read `PHASE7.md`, this tracker and ADR-0001/0004/0005 first; do not redo already-complete work. Record each new PR, CI job/run, verification and status transition here. If GitHub and tracker disagree, verify GitHub and reconcile the tracker in a documentation-only PR before proceeding.
