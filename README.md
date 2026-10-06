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
- Thumbnail page organizer with reorder / rotate / remove-page workflow
- File library with manual delete, bulk delete, and permanent-retention controls
- Job cancel/retry controls in the Web Console, with a separate `jobs:manage` scope and terminal-history cleanup

### Platform / security

- FastAPI + Next.js Web Console behind Caddy
- PostgreSQL metadata / job history
- Valkey + RQ asynchronous processing
- Service API keys + scopes + revocation + tenant/service isolation for machine-to-machine integration
- HttpOnly Web Console sessions; users are never asked to paste a service API key into the browser
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

- Web Console uses cookie sessions; when OIDC/LDAP are not configured, Next.js obtains an isolated non-admin session from an API endpoint that is reachable only on the internal Docker network
- Enabling OIDC or LDAP disables automatic Web Console login so institutional identity remains authoritative
- Service API keys remain available for machine-to-machine clients and administrative automation, not as a human login field
- Playwright browser regression coverage for both mocked APIs and the production Compose stack
- Local Admin HttpOnly session login for standalone deployments; no browser-entered bootstrap/API key
- Stable internal Web Console workspace identity across session renewal
- Upload signature validation for PDF, images, Office/OpenDocument and RTF inputs
- Admin runtime diagnostics for DB, Redis, queue/workers, storage write access, disk capacity, Gotenberg and PDF binaries
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
      |          |
      |   +------+----------+
      |   |      |          |
      | PostgreSQL Valkey  Storage
      |          |      local/NAS/S3
      |          v
      |       RQ Worker
      | qpdf / OCRmyPDF / Gotenberg
      | pypdf / ReportLab / Pillow
      | Tesseract / Poppler
      |
      +-- internal Web Console session bootstrap --> FastAPI /internal/*

Cleanup Worker ------> retention / temp cleanup
Webhook Dispatcher --> retry / dead-letter delivery
Optional ------------> ClamAV / Prometheus / OTel / Paperless / SeaweedFS
```

Gotenberg, PostgreSQL, Valkey, ClamAV, object storage, and FastAPI's `/internal/*` routes must not be published directly to the Internet. External API requests should pass through the reviewed Caddy `/api/*` routes; Web Console session bootstrap is performed server-to-server by Next.js.

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

### Production Compose override

Development keeps using `make up` / `make up-nas`. Production uses an explicit override so production-only defaults do not leak into the developer workflow:

```bash
make prod-config
make up-prod
# or, when /data is backed by the configured NAS path:
make up-prod-nas
```

`docker-compose.prod.yml` provides the production operational and runtime-hardening baseline:

- secure session cookies default to enabled;
- automatic anonymous Web Console bootstrap defaults to disabled;
- Docker JSON log rotation is enabled for all services;
- application containers run with a read-only root filesystem, `no-new-privileges`, and all Linux capabilities dropped;
- writable temporary space is explicit `tmpfs`, while document data remains on the existing data/NAS volumes;
- PID, memory, and CPU ceilings are defined for core and optional services and can be tuned through environment variables;
- production traffic is split across explicit edge, application, data, management, and egress networks; the application/data/management networks are internal;
- only Caddy is published for normal user/API traffic, while management UIs keep their existing trusted-interface binding.

Leave `PDFHUB_SESSION_COOKIE_SECURE` and `PDFHUB_WEB_CONSOLE_AUTO_LOGIN` blank in `.env` to use the development/production mode-aware defaults. Set them explicitly only when the deployment architecture requires an override.

The most commonly tuned production ceilings are documented in `.env.example` (API, worker, and Gotenberg). All remaining defaults are visible in `docker-compose.prod.yml`; change them only after observing actual host/resource usage.

Production Caddy requires an explicit `PDFHUB_PUBLIC_BIND_HOST`. Keep `127.0.0.1` when the reverse proxy is on the same host; when the upstream reverse proxy is on another machine, set this to the PDF Hub server's trusted LAN interface address rather than `0.0.0.0`.

Backup/restore tooling must use the same deployment mode through `PDFHUB_COMPOSE_MODE`:

- `default` — base Compose;
- `nas` — base + NAS override;
- `prod` — base + production override;
- `prod-nas` — base + production + NAS overrides.

## Authentication / service isolation

`PDFHUB_ADMIN_API_KEY` is a bootstrap/break-glass key with `*` scope. Use it only for administrative operations and never embed it in a browser application.

**Human Web Console authentication is session based.** The Web Console does not display a Service API Key input and does not store service credentials in React state or browser storage.

- If OIDC or LDAP is enabled, users authenticate with the configured institutional identity provider.
- If neither OIDC nor LDAP is enabled, Next.js requests an isolated, non-admin Web Console session through `/internal/web-console/session` over the private Docker network. Sessions reuse the configured stable internal workspace principal so files and job history remain available after session renewal.
- Direct calls to `/api/v1/*` still require a valid session, bearer identity, or service API key. The internal session endpoint is intentionally not exposed by Caddy's public API matcher.

Admin authorization, scopes, quotas, and service isolation remain enforced at the API layer, which is the authoritative authorization boundary. Automatic Web Console sessions are never administrators; admin access must come from an authorized institutional identity or operator-side break-glass credential.

### Local Admin / persistent internal workspace

For a standalone RCAT deployment that does not yet use OIDC/LDAP, the normal Web Console uses a stable workspace principal (`web-console:<PDFHUB_WEB_CONSOLE_WORKSPACE_ID>`) instead of a new random identity for every session. Files therefore remain visible after a browser session expires.

Create the Local Admin password hash interactively:

```bash
make local-admin-hash
```

Put the printed hash in `.env`:

```env
PDFHUB_LOCAL_ADMIN_USERNAME=admin
PDFHUB_LOCAL_ADMIN_PASSWORD_HASH=scrypt:...
PDFHUB_WEB_CONSOLE_WORKSPACE_ID=rcat-default
PDFHUB_WEB_CONSOLE_AUTO_LOGIN=true
```

Then rebuild/restart the stack and open `/admin/login`. The password itself is never stored in the repository or sent to the Web Console as an API key. Local Admin creates the same HttpOnly session type as OIDC/LDAP and should remain a break-glass/operator account; use OIDC/LDAP for named institutional users when available.

Example: create a service key for another system:

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

The plaintext API key (`pdfh_...`) is returned only once. The database stores only a keyed digest combined with the server-side pepper.

## Core API

| Method | Endpoint | Scope |
|---|---|---|
| GET / POST | `/api/v1/files` | `files:read` / `files:write` |
| GET | `/api/v1/files/{id}/download` | `files:read` |
| POST | `/api/v1/files/{id}/signed-download` | `files:read` |
| GET | `/api/v1/files/{id}/preview` | `files:read` |
| GET | `/api/v1/files/{id}/pages` | `files:read` |
| POST | `/api/v1/files/{id}/retention` | `files:write` |
| DELETE | `/api/v1/files/{id}` | `files:write` |
| POST | `/api/v1/files/bulk-delete` | `files:write` |
| GET | `/api/v1/jobs` | `jobs:read` |
| POST | `/api/v1/jobs/{id}/cancel` | `jobs:manage` |
| POST | `/api/v1/jobs/{id}/retry` | `jobs:manage` + operation scope |
| DELETE | `/api/v1/jobs/terminal` | `jobs:manage` |
| POST | `/api/v1/pdf/merge` | `pdf:merge` |
| POST | `/api/v1/pdf/organize` | `pdf:split` |
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

The direct Dependabot npm forward-patch lane is restricted to bot-only PRs that advance exactly one direct dependency while updating both `apps/web/package.json` and `apps/web/package-lock.json`, and must pass `npm ci`, typecheck, production build, and browser smoke before squash merge. All other PRs use full `make validate-free` validation and are not auto-merged.

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

- Deploy with `docker-compose.prod.yml` (`make up-prod` or `make up-prod-nas`) and terminate TLS at the reviewed edge/reverse proxy
- Generate production secrets with `make secrets`; never use example/default secrets
- For Internet-facing deployments, enable OIDC or LDAP; this automatically disables anonymous Web Console session bootstrap
- For standalone/internal deployments, set a strong `PDFHUB_LOCAL_ADMIN_PASSWORD_HASH` generated by `make local-admin-hash`; do not use Local Admin as a shared day-to-day user account
- Set `PDFHUB_WEB_CONSOLE_WORKSPACE_ID` once and keep it stable so internal Workspace ownership remains consistent across sessions
- If automatic Web Console sessions are retained, restrict Caddy access to the intended institutional/trusted network
- Never publish the FastAPI container port or `/internal/*` routes directly
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
