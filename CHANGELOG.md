# Changelog

## 0.5.1 — 2026-08-31

### Security / correctness
- Add a single-account Local Admin session mode for development and first-run testing only.
- Remove Service API Key from the human login surface; service keys remain machine-to-machine credentials managed by Admin.
- Production readiness rejects `PDFHUB_LOCAL_AUTH_ENABLED=true` so local credentials cannot be promoted accidentally.
- Human tenant ownership remains based on stable identity subject material rather than mutable display names/email.
- Add quiesced DB+storage backup consistency, restore integrity checks, stale-job reconciliation and quota concurrency hardening.
- Add worker-aware readiness, live queue/worker metrics, Alertmanager routing and production resource-isolation controls.
- Require deterministic dependency locks and `npm ci` / resolved Python requirements for image builds.

### Added
- `scripts/first-local.sh` creates random Local Admin credentials, validates the complete stack, runs real PDF workload, backup and DR gates, then installs Local CI.
- Local-auth regression tests and browser smoke coverage.
- Colorful app-style PDF tool icon treatment and explicit tool categories: document management, conversion, document decoration, and delivery/archive.
- Production environment guard that forbids local human authentication.

### Changed
- API and Web Console version advance to 0.5.1.
- User login copy now distinguishes Local Development from organization SSO.
- Admin copy explicitly identifies Service API Keys as integration credentials.
- Tool grid is grouped for faster scanning on Desktop and Mobile without removing any of the 14 PDF capabilities.

## 0.5.0 — 2026-08-31

### Security
- Validate Service API keys through `/api/v1/auth/me` before the Web Console enters authenticated state.
- Clear authentication/workspace state after failed API-key validation.
- Move the frontend baseline to Next.js 16.3.3, the reviewed August 2026 security patch baseline.
- Bind Prometheus, OpenTelemetry collector and bundled Paperless host ports to loopback by default through `PDFHUB_MANAGEMENT_BIND_HOST`.
- Require authenticated GitHub CLI access for local-CI PR enforcement instead of silently skipping PR validation.

### Added
- Playwright mocked browser smoke coverage.
- Production-stack browser smoke through Caddy → production Next.js → real FastAPI → RQ worker/storage.
- `local-ci/validate-free` and `local-ci/dependency` visible commit-status lanes plus `make local-ci-doctor`.
- PostgreSQL + local/NAS or self-hosted S3 backup tooling with manifest and SHA-256 integrity verification.
- Guarded restore with migration/readiness checks and stale RQ-state cleanup.
- Isolated disaster-recovery drill using a disposable Compose project.
- Daily systemd user backup timer tooling.
- Prometheus alert rules for API availability, 5xx ratio, p95 latency, queue backlog and repeated job failures.
- Dependency-free load/latency smoke reporting throughput, error rate and p50/p95/p99 latency.
- Unified `make release-readiness` production gate.
- `PHASE5.md` completion baseline.

### Changed
- Remove the superseded `pdf-hub-console.tsx` implementation and prune legacy Console CSS while retaining current/shared Admin primitives.
- Direct npm patch validation includes browser smoke before the narrow Dependabot auto-merge lane may merge.
- Stale PR bases receive explicit local-CI error status rather than being silently skipped.
- `make validate-free` covers release policy, operator scripts, backend, frontend, mocked browser tests, Compose and real production-stack browser runtime acceptance.
- API and Web Console version advance to 0.5.0.

## 0.4.1 — 2026-08-25

### Security
- Upgrade Pillow from 11.3.0 to 12.3.0 so the image-processing path includes the upstream 12.3.0 security fixes.
- Keep Pillow exact-pinned and enforce a reviewed secure 12.x floor (`>=12.3.0,<13.0.0`) in release-policy validation.

### Changed
- Separate version-update automation policy from security-maintenance policy: normal Dependabot configuration remains direct npm patch-only.
- Full local `make validate-free` covers Dependabot PRs outside the npm auto-merge lane and never auto-merges them.
- `scripts/validate-release-policy.py` is the single policy source of truth.
- API, Web Console and release metadata advance to 0.4.1 while the completed Phase 4 feature baseline remains 0.4.0.

## 0.4.0 — 2026-08-24

### Added
- Batch JPEG / PNG / WebP / TIFF / BMP to PDF conversion
- PDF page rasterization to PNG/JPEG with ZIP output and page-range selection
- Dedicated scopes `pdf:image-to-pdf` and `pdf:pdf-to-image`
- Stateless HMAC-signed short-lived download URLs bound to file, owner and expiry
- Dedicated download-signing secret plus configurable default/max TTL
- Persistent `webhook_deliveries` table and Phase 4 Alembic migration
- Dedicated webhook dispatcher service independent from RQ processing workers
- Exponential webhook retry with configurable attempt/backoff policy
- Dead-letter webhook state after retry exhaustion
- Admin delivery inspection and dead-letter replay endpoints
- Webhook delivery ID and attempt-number headers
- Regression tests for signed downloads, Image ↔ PDF conversion and webhook retry/DLQ lifecycle
- `PHASE4.md` completed-release documentation

### Changed
- API and Web Console version aligned to 0.4.0
- Processed job outputs support both PDF and ZIP content types
- Automatic Paperless archive is limited to PDF outputs
- Job completion/failure webhooks are queued durably instead of being sent inline by the RQ worker
- Default human scopes include the two Phase 4 media-conversion scopes

### Security
- Signed download URLs no longer require API credentials to be embedded or forwarded to recipients
- Download tokens have a hard configurable TTL ceiling and can be globally invalidated by rotating the signing secret
- Webhook hostname validation and HMAC signing are re-evaluated on every delivery attempt
- Failed webhook deliveries remain auditable and recoverable

## 0.3.0 — 2026-08-24

### Added
- OIDC Authorization Code + PKCE SSO and validated OIDC bearer tokens
- LDAP / Active Directory login with short-lived HttpOnly PDF Hub sessions
- Identity admin-group mapping while retaining service API-key authentication
- Self-hosted S3-compatible storage with bundled SeaweedFS support, plus local/NAS storage
- ClamAV INSTREAM scanning for uploads and processed outputs
- Configurable/horizontally scalable RQ workers
- Prometheus metrics and optional OpenTelemetry OTLP HTTP tracing
- Paperless-ngx manual/automatic downstream archive integration
- Alembic migrations with safe adoption of Phase 2 databases
- Production readiness endpoint at `/readyz`
- Optional Compose profiles for S3, security, observability and archive services
- Zero-cost local validation and local polling CI

### Changed
- API and Web Console version aligned to 0.3.0
- Web Console supports API Key, OIDC SSO and LDAP sessions
- Storage abstraction supports local/NAS and explicit self-hosted S3 endpoints
- Runtime service container images use explicit release baselines

## 0.2.0 — 2026-08-23

### Added
- Thai-capable text watermark
- Page numbering with custom format/position
- PDF stamp overlay
- Cached PDF preview thumbnails
- File listing endpoint
- Automatic retention cleanup service
- Per-service request rate limits, daily job quotas and storage quotas
- Allowlisted signed job-completion/failure webhooks
- Append-only JSONL audit trail and Admin audit API
- Admin UI for service keys and policies
- Expanded PDF Console for split, rotate, Office conversion and Phase 2 tools
- Compose validation in CI

### Changed
- Upgrade pypdf to 6.16.1
- Add ReportLab 5.0.0 and Noto Thai fonts
- API/Web version to 0.2.0

## 0.1.0 — 2026-08-23
- Initial PDF Hub MVP
