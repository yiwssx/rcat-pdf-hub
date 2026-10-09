# ADR-0005: Task-first journey and operations-oriented administration

- Status: **Accepted** — P7A route/input contracts and P7H.1 integration gates verified on 2026-10-09
- Date: 2026-10-09
- Related: ADR-0001 (Tool Workspace seam), ADR-0004 (Human RBAC), `PHASE7.md`, P7 Master Tracker

## Context

RCAT PDF Hub has a tool catalog, file library, processing jobs, sessions, and admin tools but its user journey is document-state-centric: `PdfHubApp` conditionally renders Document Workspace upon selection and `submit` opens Job Drawer. Tool-first entry, result return URLs and cohesive admin triage are not yet first-class. The requested change concerns navigation and task flow, not visual appearance.

## Decision

1. Provide three connected journeys: primary **Tool-first**, optional **File-first**, and administrator **Operations-first**. Keep their durable data on existing file/job and audit infrastructure.
2. Use addressable navigation for tool intent and job/result status: `/tools/[slug]`, `/jobs/[id]`, `/jobs/[id]/result`, and user-scoped My Jobs. P7A–P7D verified invalid-slug handling, back/forward, authorized file IDs and refresh recovery; these routes are now an accepted interface contract.
3. Model *presentation* journey states (intake/configuration/submission/progress/result/recovery) separately from existing persistent backend job states (`queued`/`running`/`completed`/`failed`/`cancelled`). Do not invent extra RQ statuses.
4. Preserve the deep `ToolWorkspace` seam: settings and payload construction stay there; the app shell coordinates identity, selected inputs, authorized jobs and navigation, not each tool's settings.
5. Input selection is explicit. Provide upload and owned-library selection, show file names/count and validate type, count and order before submit. Never choose another user's or an unrelated file as a fallback.
6. Make result/download/continue part of the same journey. Use the existing `output_file_id` for reusing authorized outputs without reupload, while keeping signed URLs ephemeral.
7. Organize Admin by purpose: Overview, Jobs, Access, Storage, Diagnostics and Integrations. A global job listing or cross-user action needs new explicit authorization, bounded queries, audit and negative tests; an Admin UI does not grant those rights by itself.
8. Keep `/`, `/files`, `/admin` and `/admin/login` compatible, and retain all current retention, quota, RBAC, audit and Phase 6 production constraints.

## Ownership and interfaces

| Module | Owns | Does not own |
| --- | --- | --- |
| Route / Task Journey | tool intent, navigation, visible step, input/job IDs, recovery | per-tool payload details or trusted authorization |
| ToolWorkspace | per-tool parameters, operation rules and preview | admin privileges, identity, global job listings |
| Existing Jobs and Files | durable processing status, file ownership and output relationship | cosmetic UI wizard steps |
| Admin Operations | purpose-specific telemetry, permissions and audited corrective actions | unrestricted access to personal file contents |

Favor a small behavior-focused interface at each seam. Do not add a universal workflow backend or speculative adapters when the existing job system meets the need.

## Security, failure and compatibility invariants

- Every job/result URL is checked for correct ownership and scope on the server; client navigation alone is never authorization.
- Viewer is read-only, operator stays within existing scopes, and admin-only mutations are explicit, permission-checked and auditable.
- Human session login remains session-based; never reintroduce browser API-key login.
- Invalid input, quota, offline, cancelled, failed, missing or expired jobs/files have clear recovery or terminal states; do not claim completion until the backend confirms it.
- Do not disable scanning, monitoring, retention, signed-link expiration or production readiness checks.
- No P7 plan or implementation PR mutates the published Phase 6 tag.

## Validation and acceptance evidence

P7A–P7D verified exact URLs, slug catalog, visible file selection and type/order handling, compatibility and back/forward/refresh, intake/configuration, submit, job polling, durable result and download. PR #151 passed a single queued→completed refresh→result reload→eligible next-tool, zero-reupload Playwright journey plus five Admin pages at 390px with keyboard, a11y and horizontal overflow assertions. Existing negative role/ownership checks and minimized human Admin triage remain part of the suite. Web CI #37909217495 ran 61 Playwright tests; CodeQL #37909217792 and Dependency Review #37909218130 passed. No API code changed since green Core API CI #37908227263. Admin mobile performance samples are baseline **candidates**, not enforced thresholds.

Interface decisions are accepted without granting any new backend or cross-account permission. Future contract changes must update this ADR and the canonical tracker together, and must pass the appropriate tests and security review. **ADR acceptance is not production authorization**; P7H.2 release gates, verified backup/DR and explicit operator approval remain mandatory.

## Alternatives rejected

- Making all users start with the file library.
- Separate wizard state machines and copied code for each tool.
- New workflow services, infrastructure or state stores without measured necessity.
- Unrestricted Admin inspection of cross-user documents.
- Visual imitation of a third-party product rather than improving task completion.
