# Validation status — 0.2.0

Validated in the build workspace on 2026-08-23:

- Python `compileall`: PASS
- Backend unit tests: **6 passed**
  - API-key format/hash
  - Thai-capable watermark + page-number PDF generation
  - PDF stamp overlay
  - webhook allowlist matching
  - per-service webhook-secret derivation
- PDF preview renderer (`pdftoppm`): PASS — produced PNG from a generated PDF
- TypeScript/TSX syntax transpile check: PASS for page, PDF console, Admin panel and API client
- `docker-compose.yml` YAML parse: PASS — **8 services**
- pypdf pinned to **6.16.1** (current PyPI release checked during Phase 2 work)
- ReportLab pinned to **5.0.0**

Not validated in this workspace:

- Full `docker compose build` and multi-container end-to-end run (container environment used for authoring cannot fetch all Docker/npm/pip dependencies from the Internet).
- GitHub Actions execution status; workflow is included and should validate backend, frontend production build and Compose config on GitHub runners.
- Real external webhook receiver / DNS / egress firewall behavior.

Before production deployment:

1. Run `make secrets`, populate `.env`, then `make config`.
2. Run `make up` on an Internet-connected Docker host.
3. Confirm `http://SERVER:8080/healthz`.
4. Run `make test`.
5. Exercise upload → preview → watermark → job poll → download.
6. If using webhooks, configure a narrow `PDFHUB_WEBHOOK_ALLOWED_HOSTS` and verify HMAC signatures.
7. Put Caddy behind TLS/domain or configure TLS directly before public Internet exposure.
