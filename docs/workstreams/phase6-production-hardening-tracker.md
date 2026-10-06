# Phase 6 Production Hardening & Scale — Workstream Tracker

Status: **ACTIVE / PLANNED**

Default branch: `main`

Current release baseline: `0.5.0 — Phase 5 production maturity`

Phase 6 target release: `0.6.0`

Tracker role: **canonical source of truth for Phase 6 execution status**

## Objective

Harden RCAT PDF Hub for long-term production operation without introducing unnecessary platform complexity.

Phase 6 focuses on:

- reproducible builds and software supply-chain controls;
- production container and network hardening;
- workload/worker isolation for lightweight vs CPU-heavy document jobs;
- complete self-hosted alerting and trace retention;
- role-based authorization for human users;
- scalable server-side file-library queries;
- API contract, coverage, accessibility, and performance regression gates;
- targeted architecture cleanup and final `0.6.0` release reconciliation.

Kubernetes, microservices, database clustering, and a new message broker are explicitly **out of scope** unless a later measured production constraint requires them.

## Current baseline

The repository entered Phase 6 with the following production foundation already implemented:

- FastAPI + Next.js behind Caddy;
- PostgreSQL + Valkey/RQ;
- local/NAS/self-hosted S3-compatible storage;
- session-based Web Console authentication;
- OIDC/LDAP and Local Admin support;
- scoped service API keys for machine-to-machine use;
- quotas, retention, signed downloads, durable webhooks and audit trail;
- ClamAV integration;
- Prometheus metrics/alerts and OpenTelemetry instrumentation;
- backup, checksum verification, restore and isolated DR drill;
- load/latency smoke testing and release-readiness gate;
- Playwright browser regression coverage;
- CodeQL and Dependency Review;
- project-local development-agent skills and routing rules.

Recent pre-Phase-6 hardening/refactor work:

| PR | Scope | Result |
| --- | --- | --- |
| #79 | Skill-driven UI, accessibility, Playwright and pytest hardening | MERGED |
| #80 | Deep Tool Workspace architecture seam | MERGED |
| #81 | Simplified internal ToolPanel interface | MERGED |
| #82 | CodeQL cleanup for vendored pytest skill template | MERGED |

## Phase 6 task status

| Task | Scope | Status | Primary evidence |
| --- | --- | --- | --- |
| 6.0 | Baseline verification / clean starting state | COMPLETE | Starting main `d3965ac4f0ec7fed8af01d9f4649109532334c87`; PR #84 |
| 6A.1 | Frontend reproducible install: committed npm lockfile + `npm ci` | COMPLETE | PR #85 |
| 6A.2 | Python reproducible dependency lock with transitive pins/hashes | PENDING | — |
| 6A.3 | Supply-chain scan + SBOM generation | PENDING | — |
| 6B.1 | Production Compose override/profile | PENDING | — |
| 6B.2 | Container runtime hardening | PENDING | — |
| 6B.3 | Production network-boundary hardening | PENDING | — |
| 6C.1 | Queue classification/routing | PENDING | — |
| 6C.2 | Dedicated lightweight/heavy worker pools | PENDING | — |
| 6C.3 | Per-queue observability and alerts | PENDING | — |
| 6D.1 | Self-hosted Alertmanager integration | PENDING | — |
| 6D.2 | Persistent OpenTelemetry trace backend | PENDING | — |
| 6D.3 | Self-hosted operations dashboard | PENDING | — |
| 6E.1 | Human RBAC role model and permission matrix | PENDING | — |
| 6E.2 | OIDC/LDAP group-to-role mapping | PENDING | — |
| 6E.3 | Admin effective-role/scope visibility | PENDING | — |
| 6F.1 | Server-side file pagination/search/sort/filter | PENDING | — |
| 6F.2 | Database indexes for file-library query patterns | PENDING | — |
| 6F.3 | Scalable frontend file-library UX | PENDING | — |
| 6F.4 | DB ↔ storage integrity reconciliation | PENDING | — |
| 6G.1 | OpenAPI ↔ frontend contract validation/generation | PENDING | — |
| 6G.2 | Backend coverage baseline and non-regression gate | PENDING | — |
| 6G.3 | Automated accessibility regression gate | PENDING | — |
| 6G.4 | Frontend/browser performance regression baseline | PENDING | — |
| 6H.1 | Targeted architecture cleanup | PENDING | — |
| 6H.2 | Documentation / operational runbook reconciliation | PENDING | — |
| 6H.3 | Release baseline and `v0.6.0` release | PENDING | — |

## Execution order

The planned sequence is:

```text
6.0
 ↓
6A Reproducibility & Supply Chain
 ↓
6B Container / Network Hardening
 ↓
6C Queue & Worker Isolation
 ↓
6D Alerting / Tracing / Operations Visibility
 ↓
6E Human RBAC
 ↓
6F File Library Scale & Storage Integrity
 ↓
6G Quality / Contract / Accessibility / Performance Gates
 ↓
6H Architecture Cleanup / Documentation / v0.6.0
```

A later task may move earlier only when it is a prerequisite for a safe implementation. Record any intentional reordering in the activity log.

## Workstream rules

1. Do not implement the whole phase in one PR.
2. Each PR must have one coherent objective and be independently revertible.
3. Diagnose/reproduce regressions before patching.
4. Behavior changes require regression coverage at the highest practical seam.
5. Architecture-changing work must follow the repository ADR/domain-modeling rules.
6. Do not weaken security, release, dependency, CI, backup, DR, or browser regression gates to make a PR pass.
7. Do not increase limits or disable checks merely to hide a regression.
8. Preserve the zero-paid-cloud requirement unless the project owner explicitly changes that policy.
9. Production mutations, destructive restore operations, and real deployment actions require explicit operator intent; normal implementation PRs must not perform them.
10. Do not tag or publish `v0.6.0` until 6A–6G are complete and 6H release-readiness succeeds.

## Acceptance policy

Every implementation PR must pass all applicable repository gates before merge.

Minimum expected gates:

- CodeQL;
- Dependency Review;
- Web CI for frontend changes;
- Core API CI for API/backend changes;
- release-policy validation when repository governance files change;
- relevant Playwright regression tests for browser-visible behavior;
- relevant pytest coverage for backend behavior.

Production-facing Phase 6 completion additionally requires:

- `make validate-free`;
- verified backup;
- isolated DR drill;
- deployment-target load/latency smoke;
- final `make release-readiness` in production mode.

## Phase-specific acceptance criteria

### 6A — Reproducibility & supply chain

- A clean checkout resolves the same frontend dependency graph from the committed lockfile.
- Production/frontend CI uses `npm ci`, not unconstrained `npm install`.
- Python production dependencies have a reproducible transitive lock strategy.
- Release artifacts include a machine-readable SBOM.
- The selected image/dependency scanner fails on the repository-defined unacceptable severity.

### 6B — Container / network hardening

- Development Compose remains convenient and backward-compatible.
- Production hardening is isolated in an explicit production override/profile.
- Services run with the minimum filesystem/capability/network privileges practical for their function.
- PostgreSQL, Valkey, Gotenberg and internal API endpoints remain private.
- Production Compose passes real-stack validation.

### 6C — Queue / worker isolation

- Lightweight jobs cannot be indefinitely blocked behind OCR/Office-heavy workloads.
- Every supported operation has an explicit queue class.
- Worker pools have explicit timeout/concurrency policy.
- Metrics and alerts distinguish queue classes.

### 6D — Operations visibility

- Prometheus alerts have a real self-hosted delivery path.
- OpenTelemetry traces persist in a queryable self-hosted backend instead of debug-only export.
- Operators have a single dashboard for availability, latency, queue depth, failures, workers and storage capacity.

### 6E — RBAC

- Human roles and effective scopes are explicit and testable.
- OIDC/LDAP group mapping fails closed.
- Administrative privilege is never granted by a missing/unknown mapping.
- Admin UI exposes effective identity/role/scope information without exposing credentials.

### 6F — File library scale

- Search/filter/sort/pagination are server-side.
- File-library behavior remains responsive at thousands of records.
- Query indexes are backed by measured query patterns.
- Storage reconciliation starts in dry-run/report-only mode.

### 6G — Quality gates

- Backend coverage is recorded and cannot silently regress below the accepted baseline.
- Frontend/API contract drift is detected automatically.
- Critical/serious automated accessibility findings fail the browser gate.
- Performance regression thresholds are derived from measured baseline data rather than arbitrary targets.

### 6H — Release

- Architecture cleanup is limited to evidence-backed seams/duplication.
- README, SECURITY, VALIDATION, CHANGELOG, GLOSSARY and ADRs describe the actual released system.
- Version metadata is consistent across API, frontend, documentation and release policy.
- `v0.6.0` is tagged/released only after all release-readiness evidence is complete.

## Activity log

Update this table whenever a Phase 6 task changes state or is merged.

| Date | Task | Action / Decision | Evidence | Result |
| --- | --- | --- | --- | --- |
| 2026-10-06 | Phase 6 planning | Created the Production Hardening & Scale execution plan and canonical tracker | This document | ACTIVE |
| 2026-10-06 | Architecture baseline | Tool Workspace seam and ToolPanel interface cleanup already merged before Phase 6 execution | PR #80, PR #81 | BASELINE |
| 2026-10-06 | Security baseline | Cleared current CodeQL unused-import findings from vendored pytest skill template | PR #82 | BASELINE |
| 2026-10-06 | 6.0 | Verified clean Phase 6 starting state: no open implementation PRs; recorded exact `main` SHA; added release-policy guard for tracker continuity | Starting main `d3965ac4f0ec7fed8af01d9f4649109532334c87`; PR #84 | COMPLETE |
| 2026-10-06 | 6A.1 | Committed npm lockfile; switched Web CI, Docker build, local validation and dependency validation to `npm ci`; required Dependabot manifest+lockfile synchronization | PR #85 | COMPLETE |

## Current next action

**Start Task 6A.2 — Python reproducible dependency lock.**

Introduce a reproducible transitive Python dependency lock strategy with hashes while preserving the reviewed direct dependency manifest and the existing Python security-update lane.

## Status update convention

Use only these task states:

- `PENDING`
- `IN PROGRESS`
- `BLOCKED`
- `COMPLETE`
- `SUPERSEDED`

When a task becomes `COMPLETE`, replace the evidence placeholder with the PR number and, when relevant, the exact merge/release commit or workflow run.

## Safety / resume rule

When resuming work in a later chat/session, read this tracker first.

Do **not** repeat a completed task, migration, deployment, restore, DR drill, or release operation merely because earlier conversational context is missing.

The task table and activity log are the canonical Phase 6 continuation point. If GitHub state and this document disagree, verify GitHub state first and update this tracker in a documentation-only reconciliation PR before continuing implementation.
