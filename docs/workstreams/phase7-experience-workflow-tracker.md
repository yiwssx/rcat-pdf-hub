# Phase 7 — Experience & Workflow Master Tracker

Status: **P7H.1 COMPLETE — P7H.2 RELEASE READINESS IN PROGRESS (NO DEPLOY AUTHORIZATION)**

Default branch: `main`  
Pre-planning code baseline: `4f808fd3d8e094e1d37b361ff171a021f5e02ace` (2026-10-09)  
Prior release: `v0.6.0` — Phase 6 **COMPLETE**, tag unchanged  
Phase 7 target version: **TBD at release planning**  
Tracker role: **canonical source of truth for Phase 7 execution status**

Source of scope: [PHASE7.md](../../PHASE7.md). Accepted task-first/role-safe interface: [ADR-0005](../adr/0005-task-first-journey.md).

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
| 7F.2 | Reviewed permission matrix and audited retry/cancel/repair operations where supported | COMPLETE | 7F.1 | PR #143 merged `358444d2ffb1e7cdb61eb7f41974f38cf97fa8df`; PR #144 merged `f0b9ff968d3e50415dd3d05a55030410d6d83c59` (Core API CI #37904483477, Web CI #37904483515, CodeQL #37904483467, Dependency Review #37904483464 PASS); security decision: no cross-account mutation or repair in P7 |
| 7G.1 | Human effective-role/quotas workflows; new identity mutations only after explicit security review | COMPLETE | 7E.1 | PR #146 merged `cf0dd647d202cb53ee3be83a98959c12faa62896`; Core API CI #37905364357, Web CI #37905364564, CodeQL #37905364778, Dependency Review #37905364511 PASS; accepted self-scoped read-only scope, no identity mutation |
| 7G.2 | Storage/retention/reconciliation, service keys, webhooks and integration operations with safe confirmations | COMPLETE | 7E.2, 7F.2 | PR #148 merged `7a90ca5a034c83c39707ddfe83ff3a3aac094a8f` (Core API #37907436955, Web #37907436782, CodeQL #37907436864, Dependency Review #37907436807 PASS); PR #149 merged `882ef978bb0ccfadc597debc428cca015a552074` (Core API #37908227263, Web #37908227296, CodeQL #37908227364, Dependency Review #37908227398 PASS); no automatic repair or expanded ownership |
| 7H.1 | User/Admin E2E journeys, denial tests, mobile/a11y/performance and backend regression gates | COMPLETE | 7A–7G | PR #151 merged `eb51a7bd61fe741d734c59b309a2000feb004218`; Web CI #37909217495 (61 Playwright PASS), CodeQL #37909217792 and Dependency Review #37909218130 PASS. Existing negative role/ownership regressions PASS. API code unchanged since Core API CI #37908227263 PASS (PR #149); Admin 390px keyboard/a11y/overflow PASS; candidate metrics recorded, no new performance ceilings |
| 7H.2 | Documentation, staged rollout/rollback, production verification and release gate (version TBD) | IN PROGRESS | 7H.1 | [Release-readiness handoff](phase7-release-readiness.md) drafted; local `make validate-free`, code/production release-readiness, backup/DR, operator approval, staged deployment and final release remain PENDING; no rollout authorized |

**Roll-up:** P7A–P7H.1 COMPLETE within explicitly reviewed permission boundaries. P7H.2 IN PROGRESS (documentation/evidence only). No Phase 7 production deploy, tag or release.

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

Historical design boundary for P7F.1 (implemented and verified in PR #142): the read-only human Admin triage API uses a **dedicated Admin route**. The rule below remains binding; it does not grant cross-user document access:

1. Authorize **human Admin identity server-side**; deny viewer/operator and service credentials (including wildcard-scoped service keys) unless an explicit separate security decision is recorded.
2. Require bounded filters and stable pagination (status and operation, page size ≤100); query only the fields necessary for diagnosis. Never return document contents, storage paths, input/output file IDs, raw job params or raw exception text. A masked identity/aggregate is preferred over exposing `requested_by`.
3. Log privileged triage reads with purpose and filter metadata while omitting file names, sensitive job payloads and document content. No automatic retry/cancel/repair from a read-only view.
4. Add negative authorization, leakage and query-bound tests at the API contract seam, plus Core API coverage, Web E2E, CodeQL and Dependency Review gates. Audit any state-changing operation separately under P7F.2.

This design boundary was accepted in PR #142 with negative authorization and audit tests. It is not permission to deploy.

## P7F.2 / P7G.1 acceptance decision (2026-10-09)

**P7F.2 supported action scope is owner-only.** Human Admin may inspect cross-user job **metadata** through the audited, minimal read-only triage route but cannot retry, cancel, or repair another person's work. Generic job routes enforce ownership for signed identities; existing owner-only Cancel, Retry and history-clear require persistent preaction Audit, with UI confirmation on Cancel/Retry. Unsupported generic repair and cross-account changes remain explicitly **out of scope**, not silently available. A separate design/security review and tracker must precede any future permission expansion. Existing bootstrap/service API compatibility is not a new Admin UI right. This is a scope decision that completes P7F.2 without authorizing cross-account mutations.

**P7G.1 accepted scope is current principal only.** The effective Access panel and authenticated identity response show the logged-in principal's roles, scopes, daily job allowance, storage allowance and rate limits; distinguish bootstrap quota exemption. Institutional cross-account identity lookup and role mutations are **not authorized** in P7 and require separate privacy/authorization review. This completes P7G.1 within that safe, self-scoped contract.

## P7F.1 implementation contract (2026-10-09)

- Route: `GET /api/v1/admin/jobs/triage`, separate from user/job detail APIs; no new mutations.
- Identity: server-side authenticated human Admin role from OIDC, LDAP or local-admin session; bootstrap/service/API-key and legacy-scope identities denied. Existing `/api/v1/jobs` semantics remain unchanged.
- Query: optional validated `status` and `operation`; `limit` 1–100, `offset` 0–100000; deterministic descending created_at + ID pagination.
- Data minimization: job ID, operation, status, progress, created/started/finished timestamp, boolean failure presence. No raw error, owner, file IDs, params, queue IDs, or storage locations.
- Audit: privileged read logs only filter metadata and actor; if persistence fails return HTTP 503 (fail closed). Admin UI never offers job mutations in 7F.1.
- Acceptance: negative service/legacy/operator access, contract drift, direct handler coverage, filter bounds, E2E paged read and denial. **COMPLETE** via PR #142 and its verified checks.

## P7G.2 accepted operational scope (2026-10-09)

- Existing authenticated file-owner retention editing and deletion remain owner-bound. The Admin Storage page does not gain ownership bypass or destructive repair.
- Admin Storage Health runs only upon explicit action; a dedicated human Admin endpoint records an Audit read before comparing DB/storage, returns only counts and categories, and does not reveal storage paths, file IDs or original names.
- Existing Service Key create/revoke, Service Policy changes and Webhook DLQ replay require explicit client confirmation, synchronous duplicate-action guard and persisted Audit intent before state mutation; on Audit failure, the endpoint denies the action. Replay is allowed only from `dead` state; raw Webhook errors are not exposed in Admin UI.
- These are scoped improvements to current capabilities. **No** new cross-user job/file mutation, global retention repair, account-role editing, or automatic filesystem repair is approved as part of P7. Such operations require a separately authorized security review.
- PRs #148–#149 passed Core API coverage/contract, Web E2E, CodeQL and Dependency Review. Production authorization still depends on P7H acceptance.

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
3. Preserve accepted ADR-0001 (ToolWorkspace settings ownership), ADR-0004 (RBAC), ADR-0005 (validated task-first interface) and the published Phase 6 `v0.6.0` tag.
4. ADR-0005 is `Accepted` after P7A–P7H.1 validation; future route/interface changes require explicit ADR, tracker and test updates.
5. No new workflow service, backend status type, storage engine, paid cloud dependency or UI visual rewrite by default.
6. Never disable source security scanners, coverage, API-contract, a11y/performance, backup or production release gates.
7. Use file/job ownership on every result/deep link; UI route guards do not replace server authorization.
8. Admin destructive actions require distinct confirmation and durable audit. Global jobs/users endpoints require separate threat-model review.
9. No P7 release version, tag, migration, deploy or production environment mutation without explicit P7H.2 operator approval and verified release gates.
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
| 2026-10-09 | 7F.2 | Human/session wildcard owner isolation and security action matrix merged | PR #143, merge `358444d2ffb1e7cdb61eb7f41974f38cf97fa8df`; Core API CI #37903849520, CodeQL #37903849543, Dependency Review #37903849917 | IN PROGRESS |
| 2026-10-09 | 7F.2 | Confirmed owner-scoped Cancel/Retry, synchronous duplicate prevention and fail-closed Audit Intent on cancel/retry/purge merged | PR #144, merge `f0b9ff968d3e50415dd3d05a55030410d6d83c59`; Core API CI #37904483477, Web CI #37904483515, CodeQL #37904483467, Dependency Review #37904483464 | IN PROGRESS |
| 2026-10-09 | 7G.1 | Scoped effective access accepted: current principal only; no identity mutations; limits and bootstrap exemption verified | PR #146, merge `cf0dd647d202cb53ee3be83a98959c12faa62896`; Core API CI #37905364357, Web CI #37905364564, CodeQL #37905364778, Dependency Review #37905364511 PASS | COMPLETE |
| 2026-10-09 | 7F.2 | Scope decision: cross-account job mutation/repair explicitly forbidden in P7; supported owner-only actions and Audit already tested | PRs #143–#144 + Permission Matrix; 2026-10-09 security boundary decision | COMPLETE |
| 2026-10-09 | 7G.2 | Human Admin-only Storage health with manual dry-run, redacted response, category summary, audit failure denial and responsive UI merged | PR #148, merge `7a90ca5a034c83c39707ddfe83ff3a3aac094a8f`; Core API CI #37907436955, Web CI #37907436782, CodeQL #37907436864, Dependency Review #37907436807 | IN PROGRESS |
| 2026-10-09 | 7G.2 | Preaction audit, confirmed Service Key/Policy/Webhook actions and safe error display merged | PR #149, merge `882ef978bb0ccfadc597debc428cca015a552074`; Core API CI #37908227263, Web CI #37908227296, CodeQL #37908227364, Dependency Review #37908227398 | COMPLETE |
| 2026-10-09 | 7H.1 | Begin integrated browser task→job→result→chain verification and Admin mobile overflow/a11y/keyboard/performance candidate collection | `test/p7h1-user-admin-journey-mobile`; CI pending | IN PROGRESS |

| 2026-10-09 | 7H.1 | Reconcile merged integrated user/job/result/zero-reupload Playwright suite and Admin 390px layout/keyboard/accessibility; preserve previous backend validated tree and prior denial tests | PR #151 merged `eb51a7bd61fe741d734c59b309a2000feb004218`; Web #37909217495 (61 PASS), CodeQL #37909217792, Dependency Review #37909218130 PASS; unchanged backend since Core API #37908227263 | COMPLETE |
| 2026-10-09 | 7H.2 | Start evidence-based release-readiness and rollback/stop-gate operator handoff without authorizing deployment, tag or migration | [P7 Release Readiness](phase7-release-readiness.md); exact-host local validation, DR, production check and approval pending | IN PROGRESS |

## Current next action

**P7H.2 NEXT:** Review the [release-readiness handoff](phase7-release-readiness.md), rerun exact-candidate `make validate-free` and `PDFHUB_RELEASE_MODE=code make release-readiness` on institution-owned Linux, collect backup/DR and production gate proof in an **explicitly authorized** window, and select the version only at release approval. P7H.1 PR #151 had 61 Playwright tests green, including negative role/ownership checks carried from prior waves, with backend unchanged since green Core API CI #37908227263. The single-run Admin mobile resource metrics are **candidates**, not enforced thresholds. No production rollout, tag or release authorized.

**P7H.2:** Candidate documentation and operator-runbook preparation are in progress after P7H.1 repository-level checks passed. Production/local all-in-one gates, rollback proof and explicit operator release authorization remain outstanding. No P7 production deploy, tag, migration or release before full P7H.2 acceptance.

## Tracker state protocol

Allowed statuses: `PENDING`, `IN PROGRESS`, `BLOCKED`, `COMPLETE`, `SUPERSEDED`.

When continuing in a later session, read `PHASE7.md`, this tracker and ADR-0001/0004/0005 first; do not redo already-complete work. Record each new PR, CI job/run, verification and status transition here. If GitHub and tracker disagree, verify GitHub and reconcile the tracker in a documentation-only PR before proceeding.
