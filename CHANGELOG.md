# Changelog

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
