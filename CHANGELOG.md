# Changelog

## 0.3.0 — 2026-08-24

### Added
- OIDC Authorization Code + PKCE SSO and validated OIDC bearer tokens
- LDAP / Active Directory login with short-lived HttpOnly PDF Hub sessions
- Identity admin-group mapping while retaining service API-key authentication
- S3-compatible storage for AWS S3, MinIO, SeaweedFS and Ceph RGW
- NAS deployment override
- ClamAV INSTREAM scanning for uploads and processed outputs
- Configurable/horizontally scalable RQ workers
- Prometheus metrics and optional OpenTelemetry OTLP HTTP tracing
- Paperless-ngx manual/automatic downstream archive integration
- Alembic migrations with safe adoption of Phase 2 databases
- Production readiness endpoint at `/readyz`
- Optional Compose profiles for S3, security, observability and archive services
- Phase 3 runtime acceptance for real S3-compatible storage and ClamAV scanning

### Changed
- API version to 0.3.0
- Web Console supports API Key, OIDC SSO and LDAP sessions
- File storage abstraction now stages, scans and commits to local/NAS or S3
- Worker output path is storage-backend agnostic

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
- Docker Compose now runs 8 services including cleanup worker

## 0.1.0 — 2026-08-23
- Initial PDF Hub MVP
