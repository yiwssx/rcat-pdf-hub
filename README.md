# RCAT PDF Hub

A **self-hosted, API-first** PDF processing hub that lets multiple systems share a single PDF infrastructure stack without installing duplicate PDF engines in every project.

> Status: **0.5.0 — Phase 5 production maturity**  
> Deployment target: Docker Compose on institution-owned hardware with local volumes, NAS, or self-hosted S3-compatible storage  
> Cost policy: **zero-cost software/CI/CD** — no paid runners, paid CI/CD, or paid cloud services are required

## Core capabilities

### PDF & media processing

- Merge / split / select / rotate PDFs — qpdf
- Compression — Ghostscript
- Thai + English OCR — OCRmyPDF + Tesseract `tha+eng`
- PDF/A-2
- Word / Excel / PowerPoint / LibreOffice-compatible → PDF — Gotenberg
- Thai text watermarks — pypdf + ReportLab + Noto Sans Thai
- Page numbering and PDF stamps
- PDF preview → PNG — Poppler
- Batch JPEG / PNG / WebP / TIFF / BMP → PDF
- Multi-page PDF → PNG/JPEG ZIP archive

### Platform / security

- FastAPI + Next.js Web Console behind Caddy
- PostgreSQL metadata / job history
- Valkey + RQ asynchronous processing
- Service API keys + scopes + revocation + tenant/service isolation
- OIDC Authorization Code + PKCE and LDAP/Active Directory sessions
- Per-service rate limits, daily job quotas, and storage quotas
- HMAC-signed short-lived download URLs
- Durable webhook retry / dead-letter queue / admin replay
- JSONL append-only audit trail
- ClamAV fail-closed scanning
- Local / NAS / explicit self-hosted S3-compatible storage
- Prometheus metrics + alert rules + OpenTelemetry OTLP tracing
- Paperless-ngx archive integration
- Alembic migrations, `/healthz`, and `/readyz`

### Phase 5 production maturity

- API keys are validated through `/api/v1/auth/me` before the Web Console opens an authenticated workspace
- Playwright browser regression coverage for both mocked APIs and the production Compose stack
- Next.js security baseline `16.3.3`
- Optional management ports bind to `127.0.0.1` by default
- Local CI exposes visible commit statuses for both full-validation and direct-dependency lanes
- `make local-ci-doctor` checks executor health and GitHub status reporting
- PostgreSQL + storage backups with manifests and SHA-256 integrity verification
- Guarded restore + isolated disaster-recovery drill
- Prometheus alert rules for availability, 5xx errors, latency, queue backlog, and job failures
- Dependency-free load/latency smoke test reporting p50/p95/p99
- Unified `make release-readiness` production gate

See `PHASE3.md`, `PHASE4.md`, and `PHASE5.md` for milestone details.

## Architecture

```text
Browser / Internal Systems
          |
          v
      Caddy :8080
       /       \
      v         v
 Next.js UI   FastAPI
                 |
      +----------+----------+
      |          |          |
 PostgreSQL    Valkey     Storage
                 |      local/NAS/S3
                 v
              RQ Worker
        qpdf / OCRmyPDF / Gotenberg
        pypdf / ReportLab / Pillow
        Tesseract / Poppler

Cleanup Worker ------> retention / temp cleanup
Webhook Dispatcher --> retry / dead-letter delivery
Optional ------------> ClamAV / Prometheus / OTel / Paperless / SeaweedFS
```

Gotenberg, PostgreSQL, Valkey, ClamAV, and object storage should not be published directly to the Internet. External requests should pass through the PDF Hub API/Caddy first.

## Quick start

Requirements: Docker Engine + Docker Compose plugin. **8 GB RAM** is recommended when multiple OCR/Office jobs may run concurrently.

```bash
cp .env.example .env
make secrets
# Replace the placeholders in .env with the generated secrets.
make config
make up
```

Open:

- Web Console: `http://SERVER_IP:8080`
- Swagger: `http://SERVER_IP:8080/docs`
- Health: `http://SERVER_IP:8080/healthz`
- Readiness: `http://SERVER_IP:8080/readyz`

```bash
make ps
make logs
```

## Authentication / service isolation

`PDFHUB_ADMIN_API_KEY` is a bootstrap/break-glass key with `*` scope. Use it only for administrative operations and never embed it in an application.

The platform supports machine-to-machine API keys and human login through OIDC/LDAP. Admin authorization, scopes, quotas, and service isolation are enforced at the API layer, which is the authoritative authorization boundary.

Example: create a service key:

```bash
curl -X POST http://localhost:8080/api/v1/admin/api-keys \
  -H "X-API-Key: YOUR_BOOTSTRAP_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "student-system",
    "scopes": ["files:read", "files:write", "jobs:read", "pdf:merge", "pdf:compress"],
    "rate_limit_per_minute": 120,
    "daily_job_limit": 1000,
    "max_storage_mb": 2048,
    "webhook_url": null
  }'
```

The plaintext API key (`pdfh_...`) is returned only once. The database stores only a hash combined with a server-side pepper.

## Core API

| Method | Endpoint | Scope |
|---|---|---|
| GET / POST | `/api/v1/files` | `files:read` / `files:write` |
| GET | `/api/v1/files/{id}/download` | `files:read` |
| POST | `/api/v1/files/{id}/signed-download` | `files:read` |
| GET | `/api/v1/files/{id}/preview` | `files:read` |
| GET | `/api/v1/jobs` | `jobs:read` |
| POST | `/api/v1/pdf/merge` | `pdf:merge` |
| POST | `/api/v1/pdf/images-to-pdf` | `pdf:image-to-pdf` |
| POST | `/api/v1/pdf/pdf-to-images` | `pdf:pdf-to-image` |
| POST | `/api/v1/pdf/split` | `pdf:split` |
| POST | `/api/v1/pdf/rotate` | `pdf:rotate` |
| POST | `/api/v1/pdf/compress` | `pdf:compress` |
| POST | `/api/v1/pdf/ocr` | `pdf:ocr` |
| POST | `/api/v1/pdf/pdfa` | `pdf:pdfa` |
| POST | `/api/v1/pdf/office-to-pdf` | `pdf:convert` |
| POST | `/api/v1/pdf/watermark` | `pdf:watermark` |
| POST | `/api/v1/pdf/page-numbers` | `pdf:page-number` |
| POST | `/api/v1/pdf/stamp` | `pdf:stamp` |
| POST | `/api/v1/integrations/paperless/{file_id}` | `archive:paperless` |
| GET / POST / DELETE | `/api/v1/admin/api-keys...` | `admin:keys` |
| GET / PUT | `/api/v1/admin/service-policies...` | `admin:keys` |
| GET / POST | `/api/v1/admin/webhook-deliveries...` | `admin:keys` |
| GET | `/api/v1/admin/audit` | `admin:keys` |

For the most accurate schema, use Swagger at `/docs`.

## Storage

Local storage is the default. NAS storage is supported through `docker-compose.nas.yml`.

S3-compatible mode requires an explicit `PDFHUB_S3_ENDPOINT_URL` to prevent unintended fallback to a commercial endpoint. A bundled self-hosted target is available:

```bash
make up-s3
```

```env
PDFHUB_STORAGE_BACKEND=s3
PDFHUB_S3_ENDPOINT_URL=http://seaweedfs:8333
PDFHUB_S3_BUCKET=pdfhub
PDFHUB_S3_ACCESS_KEY=<random>
PDFHUB_S3_SECRET_KEY=<random>
PDFHUB_S3_AUTO_CREATE_BUCKET=true
```

## Optional self-hosted profiles

```bash
make up-security        # ClamAV
make up-observability   # Prometheus + OpenTelemetry Collector
make up-archive         # Paperless-ngx
make up-s3              # SeaweedFS
```

Prometheus, OTLP, and Paperless management ports bind to `PDFHUB_MANAGEMENT_BIND_HOST=127.0.0.1` by default. If another management network needs access, change this value deliberately to a trusted interface/IP.

Prometheus loads rules from `ops/prometheus/alerts.yml`. Rule routing and notification destinations are infrastructure-level settings controlled by the operator and should point to the institution's chosen internal alerting system.

## Validation / local CI

Development baseline: Python **3.12**, Node **24**, Docker Engine + Compose plugin, and Playwright-compatible Chromium libraries.

```bash
make validate-policy
make validate-ops
make validate-backend
make validate-frontend
make validate-e2e
make validate-compose
make validate-runtime
# Run all validation gates.
make validate-free
```

`validate-runtime` includes a production-stack browser flow through Caddy → production Next.js → real FastAPI → worker/storage.

Warnings and deprecations are treated as failures.

Install the local polling executor on institution-owned Linux hardware:

```bash
make install-local-ci
make local-ci-status
make local-ci-doctor
```

Local CI requires the `gh` CLI to be authenticated and authorized for the repository so it can publish `local-ci/validate-free` and `local-ci/dependency` commit statuses. If authentication is unavailable, the executor fails visibly instead of silently skipping PR validation.

The direct Dependabot npm forward-patch lane is restricted to bot-only PRs that modify exactly one file, `apps/web/package.json`, and must pass typecheck, production build, and browser smoke before squash merge. All other PRs use full `make validate-free` validation and are not auto-merged.

## Backup / restore / disaster recovery

Create a consistent backup of PostgreSQL + storage:

```bash
make backup
```

Backups are stored under `PDFHUB_BACKUP_ROOT` (default `./backups`) with `manifest.env` and `SHA256SUMS`. Local/NAS and self-hosted S3-compatible storage are supported.

Verify a backup:

```bash
BACKUP=./backups/20260831T120000Z make backup-verify
```

Restore is destructive and requires explicit confirmation:

```bash
PDFHUB_RESTORE_CONFIRM=YES \
BACKUP=./backups/20260831T120000Z \
make restore
```

After restore, the system flushes only Valkey DB 0, which contains ephemeral RQ state, then runs migrations and readiness checks. This prevents stale queued jobs from pointing to mismatched metadata/storage snapshots.

Run a disaster-recovery test in an isolated Compose project without touching the production project:

```bash
BACKUP=./backups/20260831T120000Z make dr-drill
```

Install the daily backup timer as a systemd user service:

```bash
make install-backup
make backup-status
```

The default schedule is 02:30 with 14-day retention. Configure it with `PDFHUB_BACKUP_ON_CALENDAR`, `PDFHUB_BACKUP_ROOT`, and `PDFHUB_BACKUP_RETENTION_DAYS`.

## Load / release readiness

Run the load smoke test without adding a Python dependency:

```bash
URL=http://localhost:8080 \
REQUESTS=100 CONCURRENCY=10 \
MAX_ERROR_RATE=0.01 MAX_P95_MS=1500 \
make load-smoke
```

Code-only release gate:

```bash
PDFHUB_RELEASE_MODE=code make release-readiness
```

The production gate requires a verifiable backup and a deployment URL. It runs a DR drill by default:

```bash
BACKUP=./backups/20260831T120000Z \
URL=https://pdf.example.org \
make release-readiness
```

## Production checklist

- Use a real TLS/domain configuration and set `PDFHUB_SESSION_COOKIE_SECURE=true`
- Generate production secrets with `make secrets`; never use example/default secrets
- Enable ClamAV fail-closed scanning for externally supplied files
- Restrict `PDFHUB_WEBHOOK_ALLOWED_HOSTS`
- Keep management ports on loopback or a trusted management network
- Enable the backup timer and test restore/DR periodically
- Review Prometheus alerts and connect rule routing to the selected internal alerting system
- Run `make release-readiness` before significant production releases

## Phase completion

- Phase 1 — MVP / core processing
- Phase 2 — advanced PDF, quota, audit, administration
- Phase 3 — production / enterprise foundation (`0.3.0`)
- Phase 4 — image conversion, signed delivery, durable webhook (`0.4.0`; `0.4.1` maintenance)
- **Phase 5 — production maturity (`0.5.0`) — A/B/C implementation baseline complete**

## License

MIT applies to source code in this repository. See `LICENSE`; dependencies remain under their respective upstream licenses.
