# Phase 7 — Task-first Experience & Operational Workflows

Status: **P7A–P7H.1 VERIFIED; P7H.2 RELEASE READINESS IN PROGRESS — NO PRODUCTION APPROVAL**

Base: RCAT PDF Hub `v0.6.0`. Preserve the published Phase 6 release and security/production gates.

Canonical tracker: [P7 Master Tracker](docs/workstreams/phase7-experience-workflow-tracker.md). Design decision: [ADR-0005](docs/adr/0005-task-first-journey.md) (**Accepted** after P7A route/input validation).

## Goal

Improve how users complete existing document tasks and how administrators diagnose and manage the service. Borrow the *task-first workflow pattern* common to PDF tools without copying iLovePDF's visual identity, requiring new paid services, or changing the existing candy-style UI design.

- **Tool-first (primary):** choose tool → upload/select files → configure/preview → process/track → result/download/continue.
- **File-first (secondary):** My Files → choose file(s) → choose eligible tool → configure/process → result.
- **Operations-first Admin:** overview → triage issue → scoped diagnosis → authorized action → verify/audit outcome.

## Code baseline and constraints

- `PdfHubApp` coordinates session, file selection, jobs, and view selection.
- `ToolWorkspace` owns tool-specific settings and payload construction (ADR-0001). Preserve that seam.
- `v3-ui.tsx` exposes Home, Document Workspace, Files, and Job Drawer. After submit, the global Job Drawer currently opens rather than a durable result route.
- Routes currently include `/`, `/files`, `/admin`, and `/admin/login`. Preserve compatibility.
- Existing FastAPI jobs, `output_file_id`, file library, PostgreSQL, Valkey/RQ pools, retention, session auth, roles, audit, observability, and deployment stack remain authoritative.
- Role management beyond existing viewer/operator/admin mapping, admin-global job list/action permissions, and new result routes need scoped design before implementation.

Do not add a separate workflow engine, new database/message broker, unbounded privileged job access or third-party assets merely to implement this phase. Version and deployment decisions are deferred; Phase 6 tag `v0.6.0` is immutable.

## Delivery sequence

| Wave | Outcome | Dependencies |
| --- | --- | --- |
| P7A | Tool deep links, explicit upload/library intake and validation | P7 planning |
| P7B | Unified configuration and client journey states | P7A |
| P7C | Queued/running/error feedback, durable result, download and next-tool handoff | P7B |
| P7D | My Jobs, My Files bidirectional navigation and refresh recovery | P7C |
| P7E | Admin information architecture and actionable Overview | P7 planning |
| P7F | Admin job triage, safe operations and diagnostics | P7E |
| P7G | Scoped access/quotas, storage, retention and integration flows | P7E/P7F |
| P7H | Journey E2E, security, accessibility, performance, staged rollout/release gate | P7A–P7G |

Track each independently revertible implementation PR, dependencies, actual test evidence, and status in the [P7 Master Tracker](docs/workstreams/phase7-experience-workflow-tracker.md). Admin navigation can proceed in parallel with user journeys if it does not change shared auth/job semantics.

## Definition of done

- A user has a clear next action throughout the task, can resume an authorized job after refresh, and can download or chain completed files without uploading again.
- No implicit selection of unrelated files; failures, expired outputs, missing permissions and offline states provide understandable recovery.
- Admin workflows present purpose-specific diagnostics and audited, explicitly scoped actions; no unauthorized cross-user document access.
- Existing UI visual style, RBAC, quota/retention, audit, API contract, coverage, CodeQL, supply-chain, accessibility/performance and runtime validation stay intact.
- Completion rates, latency targets and journey improvements are measured during P7H; do not assert unmeasured results.

## Planning handoff and execution continuity

The planning-only PR #128 was followed by owner-authorized implementation on 2026-10-09. P7A–P7G have been merged and validated through scoped PRs #129–#149. P7F.2 explicitly retains **owner-only job actions**; P7F.1 has bounded audited, redacted human Admin triage reads only; P7G.1 has **self-scoped** identity/quota introspection; P7G.2 retains audited confirmation and dry-run boundaries. No cross-user mutation, global repair or new role editing is approved.

**P7H.1 COMPLETE:** PR #151 merged to `main` as `eb51a7bd61fe741d734c59b309a2000feb004218`. Web CI #37909217495 passed 61 Playwright tests (including queued→completed→result→next-tool handoff, Admin 390px layout, keyboard activation and a11y); CodeQL #37909217792 and Dependency Review #37909218130 passed. The backend did not change after the passing Core API CI #37908227263 from PR #149. Recorded Admin resource measurements are candidates, not automatically accepted performance budgets.

**P7H.2 IN PROGRESS:** Documentation/operator gate preparation only. See [P7 Release Readiness](docs/workstreams/phase7-release-readiness.md) and the [Master Tracker](docs/workstreams/phase7-experience-workflow-tracker.md). Exact-candidate local `make validate-free`, code and production readiness, backup/DR, staging/rollback, release version selection and explicit deployment approval are **outstanding**. **No Phase 7 production deployment, migration, tag or release is authorized by these docs or by PR merges.** The prior published `v0.6.0` remains immutable.
