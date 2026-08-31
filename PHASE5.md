# Phase 5 — Production Maturity

Status: completed implementation baseline for release 0.5.0.

Phase 5 turns the completed Phase 4 feature set into an operationally mature service. It is intentionally split into three hardening tracks so security, validation and recovery remain explicit and independently reviewable.

## Phase 5A — Frontend and production hardening

Completed baseline:

- Service API keys are validated through `/api/v1/auth/me` before the Web Console enters authenticated state.
- Failed key validation clears authentication/workspace state.
- Browser smoke tests cover invalid and valid API-key login plus Workspace, preview, job/download and upload flows.
- Browser mocks require protected requests to carry the expected API key, preventing false-green authentication regressions.
- A production-stack browser smoke test exercises Caddy -> production Next.js -> real FastAPI -> worker/storage using the runtime Compose stack.
- The superseded Web Console implementation and legacy Console CSS are removed/pruned.
- Prometheus, OTLP and Paperless management ports bind to loopback by default.
- Next.js is on the August 2026 Active LTS security patch baseline `16.3.3`.

## Phase 5B — Validation, CI and security hardening

Completed baseline:

- `make validate-free` covers release policy, backend tests, frontend typecheck/build, mocked browser smoke, Compose validation, runtime acceptance and production-stack browser smoke.
- Direct npm patch validation also runs browser smoke before the narrow Dependabot auto-merge lane may merge a dependency update.
- Local CI posts visible pending/success/failure/error commit statuses for both full-validation and direct-dependency lanes.
- Stale PR bases receive an explicit error status instead of being silently skipped.
- `scripts/local-ci-doctor.sh` checks toolchain versions, Docker/Compose, GitHub CLI authentication, repository access and systemd timer/service state.
- Local CI installation requires authenticated GitHub CLI when PR validation/status reporting is expected.
- Release policy verifies the Phase 5 validation, operations and monitoring baseline without relying on one brittle source-code string match.
- Admin APIs remain backend-authorized; the UI hardening baseline documents that authorization is authoritative even when navigation is visible.

## Phase 5C — Operational maturity

Completed baseline:

- Consistent backup tooling captures PostgreSQL plus local/NAS PDF data, or PostgreSQL plus self-hosted S3 objects.
- Backup manifests include release, git SHA, storage backend, timestamp and SHA-256 integrity checks.
- Restore requires explicit destructive confirmation and validates checksums before database/storage replacement.
- Daily systemd user backup timer installation is provided with configurable retention.
- An isolated disaster-recovery drill restores a backup into a disposable Compose project, checks `/healthz` and `/readyz`, then tears the drill environment down.
- Prometheus alert rules cover API availability, 5xx error ratio, p95 latency, queue backlog and repeated job failures.
- A standard-library load smoke tool reports success rate plus p50/p95/p99 latency and enforces configurable thresholds.
- Release-readiness tooling combines validation, backup verification/creation and optional target load smoke into one operator gate.

## Release gate

Before merging/releasing Phase 5:

1. `make local-ci-doctor`
2. `make validate-free`
3. `make backup`
4. `make backup-verify BACKUP=<path>`
5. `make dr-drill BACKUP=<path>` on an operator-approved validation host
6. `make load-smoke URL=https://pdf.example.org` against the intended deployment endpoint
7. Confirm `local-ci/validate-free` is successful on the release PR head.

Phase 5 does not add a paid CI, hosted runner or commercial-cloud requirement. Production backup destinations, external self-hosted S3 snapshots and downstream Paperless backup remain operator-controlled infrastructure choices.
