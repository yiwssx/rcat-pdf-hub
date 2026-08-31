# Changelog

## Unreleased — Phase 5A hardening

### Fixed
- Validate Service API keys through `/api/v1/auth/me` before the Web Console enters authenticated state, preventing invalid keys from exposing a misleading connected UI.

### Added
- Playwright Chromium smoke coverage for invalid/valid API-key login, Workspace load, PDF preview, job submission/download and file upload.
- `make validate-e2e` and mandatory browser smoke execution inside `make validate-free`.
- Release-policy assertions that preserve the API-key authentication fix, browser smoke baseline and loopback management bindings.

### Changed
- Remove the superseded `pdf-hub-console.tsx` implementation and prune legacy Console CSS while retaining shared/Admin primitives.
- Prometheus, OpenTelemetry collector and bundled Paperless host ports now bind to `127.0.0.1` by default through `PDFHUB_MANAGEMENT_BIND_HOST`; widening access is an explicit trusted-management-network choice.

## 0.4.1 — 2026-08-25

### Security
- Upgrade Pillow from 11.3.0 to 12.3.0 so the image-processing path includes the upstream 12.3.0 security fixes.
- Keep Pillow exact-pinned and enforce a reviewed secure 12.x floor (`>=12.3.0,<13.0.0`) in release-policy validation.

### Changed
- Separate version-update automation policy from security-maintenance policy: normal Dependabot configuration remains direct npm patch-only.
- Full local `make validate-free` now covers Dependabot PRs outside the npm auto-merge lane, including pip/security PRs, and never auto-merges them.
- Remove duplicated release-policy logic from `validate-free.sh`; `scripts/validate-release-policy.py` is now the single policy source of truth.
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
- Processed job outputs now support both PDF and ZIP content types
- Automatic Paperless archive is limited to PDF outputs
- Job completion/failure webhooks are queued durably instead of being sent inline by the RQ worker
- Default human scopes include the two Phase 4 media-conversion scopes
- Release-policy validation now enforces Phase 4 metadata, migration, tests and dispatcher configuration

### Security
- Signed download URLs no longer require API credentials to be embedded or forwarded to download recipients
- Download tokens have a hard configurable TTL ceiling and can be globally invalidated by rotating the signing secret
- Webhook hostname validation and HMAC signing are re-evaluated on every delivery attempt
- Failed webhook deliveries remain auditable and recoverable instead of disappearing after transient failure

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
- Phase 3 runtime acceptance for real self-hosted S3-compatible storage and ClamAV scanning
- Zero-cost local validation for backend, frontend, Compose and runtime
- Optional zero-cost local CI polling executor and direct-dependency validator
- Release-policy validation for zero-cost configuration, dependency scope and frozen container baselines

### Changed
- API and Web Console version aligned to 0.3.0
- Web Console supports API Key, OIDC SSO and LDAP sessions
- File storage abstraction now stages, scans and commits to local/NAS or explicit self-hosted S3 endpoints
- S3 mode now refuses startup/use without `PDFHUB_S3_ENDPOINT_URL`, preventing implicit commercial-cloud fallback
- Worker output path is storage-backend agnostic
- Documentation and examples use self-hosted/free infrastructure only
- Dependabot is limited to direct npm dependencies in `apps/web/package.json` and configured to generate patch updates only; transitive, lockfile, pip, Docker and GitHub Actions updates are excluded
- GitHub-hosted Actions workflows were removed to guarantee zero paid CI exposure
- Python, Node and runtime service container images are pinned to explicit release baselines so Docker pulls cannot silently upgrade infrastructure

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
- Docker Compose now runs 8 core services including cleanup worker

## 0.1.0 — 2026-08-23
- Initial PDF Hub MVP
