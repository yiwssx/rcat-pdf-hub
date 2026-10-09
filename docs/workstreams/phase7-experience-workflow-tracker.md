# Phase 7 — Experience & Workflow Master Tracker

Status: **IN PROGRESS — P7F.2 PERMISSIONS / AUDITED ACTIONS**

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
| 7B.1 | Unified client journey state transitions, back/cancel, duplicate-submit guard, per-tool capability metadata | COMPLETE | 7A.2 | PR #131 merged as `b97c9ad62699bbbdf8d7cf21678c58d10c6909ef`; Web CI #37895653343, CodeQL #37895653364, Dependency Review #37895653338 PASS |
| 7B.2 | Configure/preview/submit contract using current ToolWorkspace and one primary action | COMPLETE | 7B.1 | PR #132 merged `d8c193270ee430459d3b6325676bd60a09c2e829`; Web CI #37896155601, CodeQL #37896155568, Dependency Review #37896155388 PASS |
| 7C.1 | Job detail/progress surface for queued/running/completed/failed/cancelled; polling and error recovery | COMPLETE | 7B.2 | PR #134 merged `04382a1f763abf900f9cf3520eba2383fb06b05c`; Web CI #37897501924, CodeQL #37897501993, Dependency Review #37897501952 PASS |
| 7C.2 | Durable authenticated result route; correct output/expiry handling; primary download action | COMPLETE | 7C.1 | PR #135 merged `b6e5e538dc88fc77161d25a420a364bf460e47b0`; Web CI #37898003345, CodeQL #37898003319, Dependency Review #37898003281 PASS |
| 7C.3 | Continue with eligible tool via `output_file_id` without downloading/reuploading | COMPLETE | 7C.2 | PR #136 merged `07e61f77754b03a331b411ebf0055cd5f3f27354`; Web CI #37898421603, CodeQL #37898421476, Dependency Review #37898421573 PASS |
| 7D.1 | User-scoped My Jobs history/status filtering; reopen active or prior jobs | COMPLETE | 7C.2 | PR #137 merged `736e37a043e876239209ca4a6db663ec3e4b7234`; Core API CI #37899707311, Web CI #37899707395, CodeQL #37899707403, Dependency Review #37899707323 PASS |
| 7D.2 | My Files ↔ tools ↔ result navigation; refresh recovery and expired/missing file states | COMPLETE | 7D.1 | PR #138 merged `925e37703e74b6a9e90f4c613d4345061730664b`; Web CI #37900286145, CodeQL #37900286158, Dependency Review #37900286173 PASS |
| 7E.1 | Admin information architecture: Overview, Jobs, Access, Storage, Diagnostics, Integrations | COMPLETE | 7.0 | PR #139 merged `5262ad3006d9707437bbe03940a560118bbce739`; Web CI #37901082307, CodeQL #37901082288, Dependency Review #37901082306 PASS |
| 7E.2 | Actionable Admin Overview based on existing availability, jobs, queue and storage status | COMPLETE | 7E.1 | PR #140 merged `fb5af25da258db38efca677d590cd694608822a6`; Web CI #37901625014, CodeQL #37901624801, Dependency Review #37901624950 PASS |
| 7F.1 | Read-only Admin job triage by queue/status/failure; scoped diagnostics, bounded queries | COMPLETE | 7E.2 | PR #142 merged `804643b5df5ec536e353769ce004641e09ac0a98`; Core API CI #37902944481, Web CI #37902944329, CodeQL #37902944366, Dependency Review #37902944332 PASS |
| 7F.2 | Reviewed permission matrix and audited retry/cancel/repair operations where supported | IN PROGRESS | 7F.1 | `fix/p7f2-human-admin-job-ownership`: permission matrix and owner-scope hardening; action approval pending |
| 7G.1 | Human effective-role/quotas workflows; new identity mutations only after explicit security review | PENDING | 7E.1 | — |
| 7G.2 | Storage/retention/reconciliation, service keys, webhooks and integration operations with safe confirmations | PENDING | 7E.2, 7F.2 | — |
| 7H.1 | User/Admin E2E journeys, denial tests, mobile/a11y/performance and backend regression gates | PENDING | 7A–7G | — |
| 7H.2 | Documentation, staged rollout/rollback, production verification and release gate (version TBD) | PENDING | 7H.1 | — |

**Roll-up:** P7A–P7E COMPLETE; P7F IN PROGRESS (7F.1 merged; 7F.2 permission hardening active); P7G–P7H PENDING. No Phase 7 deploy or release.

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

## P7F security boundary (review before implementation)

P7F.1 is not yet implemented or authorized for cross-user document access. A purpose-limited read-only job triage API must use a **dedicated Admin route**, not silently reuse a user-scoped `/jobs` response or treat a UI flag as authorization:

1. Authorize **human Admin identity server-side**; deny viewer/operator and service credentials (including wildcard-scoped service keys) unless an explicit separate security decision is recorded.
2. Require bounded filters and stable pagination (status and operation, page size ≤100); query only the fields necessary for diagnosis. Never return document contents, storage paths, input/output file IDs, raw job params or raw exception text. A masked identity/aggregate is preferred over exposing `requested_by`.
3. Log privileged triage reads with purpose and filter metadata while omitting file names, sensitive job payloads and document content. No automatic retry/cancel/repair from a read-only view.
4. Add negative authorization, leakage and query-bound tests at the API contract seam, plus Core API coverage, Web E2E, CodeQL and Dependency Review gates. Audit any state-changing operation separately under P7F.2.

This handoff is a proposed review boundary, not permission to deploy or a claim that P7F.1 is complete.

## P7F.1 implementation contract (2026-10-09)

- Route: `GET /api/v1/admin/jobs/triage`, separate from user/job detail APIs; no new mutations.
- Identity: server-side authenticated human Admin role from OIDC, LDAP or local-admin session; bootstrap/service/API-key and legacy-scope identities denied. Existing `/api/v1/jobs` semantics remain unchanged.
- Query: optional validated `status` and `operation`; `limit` 1–100, `offset` 0–100000; deterministic descending created_at + ID pagination.
- Data minimization: job ID, operation, status, progress, created/started/finished timestamp, boolean failure presence. No raw error, owner, file IDs, params, queue IDs, or storage locations.
- Audit: privileged read logs only filter metadata and actor; if persistence fails return HTTP 503 (fail closed). Admin UI never offers job mutations in 7F.1.
- Acceptance: negative service/legacy/operator access, contract drift, direct handler coverage, filter bounds, E2E paged read and denial. `PENDING` until PR merge and verified CI.

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
| 2026-10-09 | 7B.1 | Added accessible journey steps, capability metadata, guarded concurrent submits; merged with Playwright validation | PR #131, merge `b97c9ad62699bbbdf8d7cf21678c58d10c6909ef`; Web CI #37895653343, CodeQL #37895653364, Dependency Review #37895653338 | COMPLETE |
| 2026-10-09 | 7B.2 | Validated single/multi-file configuration and preview/submit contract; merged after Playwright, CodeQL and dependency gates | PR #132, merge `d8c193270ee430459d3b6325676bd60a09c2e829`; Web CI #37896155601, CodeQL #37896155568, Dependency Review #37896155388 | COMPLETE |
| 2026-10-09 | 7C.1 | Durable job status, polling, scoped denial/error recovery and retry tested; merged after full CI | PR #134, merge `04382a1f763abf900f9cf3520eba2383fb06b05c`; Web CI #37897501924, CodeQL #37897501993, Dependency Review #37897501952 | COMPLETE |
| 2026-10-09 | 7C.2 | Authenticated result route, original-name downloads, expiry/missing/403/410 recovery validated and merged | PR #135, merge `b6e5e538dc88fc77161d25a420a364bf460e47b0`; Web CI #37898003345, CodeQL #37898003319, Dependency Review #37898003281 | COMPLETE |
| 2026-10-09 | 7C.3 | Compatible tool links retain output ID with no duplicate POST upload, tested PDF/image/expired paths | PR #136, merge `07e61f77754b03a331b411ebf0055cd5f3f27354`; Web CI #37898421603, CodeQL #37898421476, Dependency Review #37898421573 | COMPLETE |
| 2026-10-09 | 7D.1 | Owner-scoped My Jobs, bounded status/page filters, direct handler/HTTP auth tests, backend coverage retained; merged | PR #137, merge `736e37a043e876239209ca4a6db663ec3e4b7234`; Core API CI #37899707311, Web CI #37899707395, CodeQL #37899707403, Dependency Review #37899707323 | COMPLETE |
| 2026-10-09 | 7D.2 | File-first route, deep-link recovery beyond listing limit and expiry/denial paths merged after regressions | PR #138, merge `925e37703e74b6a9e90f4c613d4345061730664b`; Web CI #37900286145, CodeQL #37900286158, Dependency Review #37900286173 | COMPLETE |
| 2026-10-09 | 7E.1 | Six deep-link Admin areas with isolated panels and non-admin denial merged | PR #139, merge `5262ad3006d9707437bbe03940a560118bbce739`; Web CI #37901082307, CodeQL #37901082288, Dependency Review #37901082306 | COMPLETE |
| 2026-10-09 | 7E.2 | Operational status-to-diagnostic links and safe retry validated with browser regressions; merged | PR #140, merge `fb5af25da258db38efca677d590cd694608822a6`; Web CI #37901625014, CodeQL #37901624801, Dependency Review #37901624950 | COMPLETE |
| 2026-10-09 | 7F.1 | Minimized human Admin triage with bounded filters, audit gate, negative tests and UI merged | PR #142, merge `804643b5df5ec536e353769ce004641e09ac0a98`; Core API CI #37902944481, Web CI #37902944329, CodeQL #37902944366, Dependency Review #37902944332 | COMPLETE |
| 2026-10-09 | 7F.2 | Start ownership-bound general job APIs and documented action matrix; cross-account mutations remain gated | `fix/p7f2-human-admin-job-ownership`; PR/CI pending | IN PROGRESS |

## Current next action

**P7F.2 execution:** Secure general jobs API ownership for all identity/session callers (including human Admin and legacy wildcard) without altering bootstrap API compatibility. Record reviewed role/action matrix in `docs/workstreams/phase7-f2-permission-matrix.md`. Cross-account mutations require separately approved authorization, stable status preconditions and fail-closed audit; do not label 7F.2 complete yet. Run Core API, Web, CodeQL and Dependency Review on final commit; no deploy/tag before P7H.

## Tracker state protocol

Allowed statuses: `PENDING`, `IN PROGRESS`, `BLOCKED`, `COMPLETE`, `SUPERSEDED`.

When continuing in a later session, read `PHASE7.md`, this tracker and ADR-0001/0004/0005 first; do not redo already-complete work. Record each new PR, CI job/run, verification and status transition here. If GitHub and tracker disagree, verify GitHub and reconcile the tracker in a documentation-only PR before proceeding.
