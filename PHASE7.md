# Phase 7 — Task-first Experience & Operational Workflows

Status: **IMPLEMENTATION IN PROGRESS — P7G.2 (P7F AND P7G.1 COMPLETE AT REVIEWED SCOPE)**

Base: RCAT PDF Hub `v0.6.0`. Preserve the published Phase 6 release and security/production gates.

Canonical tracker: [P7 Master Tracker](docs/workstreams/phase7-experience-workflow-tracker.md). Design decision: [ADR-0005](docs/adr/0005-task-first-journey.md) (**Proposed** pending P7A technical validation).

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

**The Phase 7 planning PR #128 was documentation/governance only.** No P7 implementation, migrations, production deployment, retagging or release is authorized by the planning request. Execution was explicitly requested on 2026-10-09. P7A.1 merged in PR #129 with tested tool deep links. P7A.2 merged in PR #130 after browser, CodeQL and dependency gates. P7B.1 merged in PR #131. P7B.2 merged in PR #132. P7A and P7B are complete; P7C.1 merged in PR #134. P7C.2 merged in PR #135. P7C.3 merged in PR #136. P7A–P7C are complete; P7D.1 merged in PR #137. P7D.2 merged in PR #138. P7A–P7D are complete; P7E.1 merged in PR #139; P7E.2 merged in PR #140; P7A–P7E complete. P7F–P7H pending, with P7F.1 requiring explicit scoped Admin-read authorization and data-minimization review, with no Phase 7 production deployment or release, and there is no Phase 7 deployment or release authorization.
