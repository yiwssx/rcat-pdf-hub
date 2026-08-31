# RCAT PDF Hub

ศูนย์กลางประมวลผล PDF แบบ **self-hosted / API-first** สำหรับให้หลายระบบใช้ PDF infrastructure ชุดเดียว โดยไม่ต้องติดตั้ง engine PDF ซ้ำในทุกโปรเจกต์

> Status: **0.5.0 — Phase 5 production maturity**
> Deployment target: Docker Compose บนเครื่องขององค์กร รองรับ local volume, NAS และ self-hosted S3-compatible storage
> Cost policy: **zero-cost software/CI/CD** — ไม่พึ่ง paid runner, paid CI/CD หรือ paid cloud service

## ความสามารถหลัก

### PDF & media processing

- รวม / แยก / เลือก / หมุน PDF — qpdf
- บีบอัด — Ghostscript
- OCR ไทย + อังกฤษ — OCRmyPDF + Tesseract `tha+eng`
- PDF/A-2
- Word / Excel / PowerPoint / LibreOffice-compatible → PDF — Gotenberg
- Watermark ภาษาไทย — pypdf + ReportLab + Noto Sans Thai
- เลขหน้าและ PDF Stamp
- Preview PDF → PNG — Poppler
- JPEG / PNG / WebP / TIFF / BMP หลายไฟล์ → PDF
- PDF → PNG/JPEG หลายหน้าเป็น ZIP

### Platform / security

- FastAPI + Next.js Web Console ผ่าน Caddy
- PostgreSQL metadata / job history
- Valkey + RQ asynchronous processing
- Service API Key + scopes + revoke + tenant/service isolation
- OIDC Authorization Code + PKCE และ LDAP/Active Directory session
- Per-service rate limit, daily job quota และ storage quota
- HMAC signed short-lived download URL
- Durable webhook retry / dead-letter queue / admin replay
- JSONL append-only audit trail
- ClamAV fail-closed scanning
- Local / NAS / explicit self-hosted S3-compatible storage
- Prometheus metrics + alert rules + OpenTelemetry OTLP tracing
- Paperless-ngx archive integration
- Alembic migration, `/healthz`, `/readyz`

### Phase 5 production maturity

- API key ถูกตรวจผ่าน `/api/v1/auth/me` ก่อน Web Console เปิด authenticated workspace
- Playwright browser regression ทั้ง mocked API และ production Compose stack
- Next.js security baseline `16.3.3`
- Optional management ports bind `127.0.0.1` โดย default
- Local CI มี visible commit status ทั้ง full-validation และ direct dependency lane
- `make local-ci-doctor` ตรวจ health ของ executor และ GitHub status reporting
- PostgreSQL + storage backup พร้อม manifest และ SHA-256 integrity
- guarded restore + isolated disaster-recovery drill
- Prometheus alert rules สำหรับ availability, 5xx, latency, queue backlog และ job failure
- dependency-free load/latency smoke ที่วัด p50/p95/p99
- unified `make release-readiness` production gate

รายละเอียด milestone ดู `PHASE3.md`, `PHASE4.md` และ `PHASE5.md`

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

Gotenberg, PostgreSQL, Valkey, ClamAV และ object storage ไม่ควร publish ตรงสู่ Internet ทุก request ภายนอกควรผ่าน PDF Hub API/Caddy ก่อน

## Quick start

ต้องมี Docker Engine + Docker Compose plugin แนะนำ RAM **8 GB** หากใช้ OCR/Office พร้อมกันหลายงาน

```bash
cp .env.example .env
make secrets
# นำ secret ที่ได้ไปแทน placeholder ใน .env
make config
make up
```

เปิด:

- Web Console: `http://SERVER_IP:8080`
- Swagger: `http://SERVER_IP:8080/docs`
- Health: `http://SERVER_IP:8080/healthz`
- Readiness: `http://SERVER_IP:8080/readyz`

```bash
make ps
make logs
```

## Authentication / Service isolation

`PDFHUB_ADMIN_API_KEY` เป็น bootstrap/break-glass key ที่มี scope `*` ควรใช้เฉพาะงานผู้ดูแลและไม่ฝังใน application

ระบบรองรับ machine-to-machine API key และ human login ผ่าน OIDC/LDAP การอนุญาต admin, scopes, quota และ service isolation ถูกบังคับที่ API layer ซึ่งเป็น authoritative authorization boundary

ตัวอย่างสร้าง service key:

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

plaintext API key (`pdfh_...`) ถูกคืนครั้งเดียว จากนั้นฐานข้อมูลเก็บเฉพาะ hash ที่ผสม server-side pepper

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

รายละเอียด schema ที่แม่นที่สุดดูจาก Swagger `/docs`

## Storage

Default คือ local storage และสามารถใช้ NAS ผ่าน `docker-compose.nas.yml`

S3-compatible mode บังคับ `PDFHUB_S3_ENDPOINT_URL` อย่างชัดเจน เพื่อป้องกัน implicit fallback ไปยัง commercial endpoint โดยไม่ได้ตั้งใจ ตัวอย่าง bundled self-hosted target:

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

Management ports ของ Prometheus, OTLP และ Paperless bind ที่ `PDFHUB_MANAGEMENT_BIND_HOST=127.0.0.1` โดย default หากต้องเปิดให้ management network อื่นเข้าถึง ให้เปลี่ยนเป็น trusted interface/IP โดยตั้งใจ

Prometheus โหลด rules จาก `ops/prometheus/alerts.yml`; rule routing/notification destination เป็นการตั้งค่าของผู้ดูแล infrastructure ตามระบบแจ้งเตือนภายในองค์กร

## Validation / local CI

Development baseline: Python **3.12**, Node **24**, Docker Engine + Compose plugin และ Playwright-compatible Chromium libraries

```bash
make validate-policy
make validate-ops
make validate-backend
make validate-frontend
make validate-e2e
make validate-compose
make validate-runtime
# ทั้งหมด
make validate-free
```

`validate-runtime` รวม production-stack browser flow ผ่าน Caddy → production Next.js → real FastAPI → worker/storage

Warnings และ deprecations ถือเป็น failure

ติดตั้ง local polling executor บนเครื่อง Linux ขององค์กร:

```bash
make install-local-ci
make local-ci-status
make local-ci-doctor
```

Local CI ต้องมี `gh` CLI ที่ authenticate และเข้าถึง repository ได้ เพื่อโพสต์ `local-ci/validate-free` และ `local-ci/dependency` commit status; หาก authentication ใช้งานไม่ได้ executor จะ fail แบบมองเห็นได้แทนการข้าม PR validation เงียบ ๆ

Direct Dependabot npm forward-patch lane ถูกจำกัดเฉพาะ bot-only PR ที่เปลี่ยน `apps/web/package.json` หนึ่งไฟล์ และต้องผ่าน typecheck, production build และ browser smoke ก่อน squash merge ส่วน PR อื่นใช้ full `make validate-free` และไม่ auto-merge

## Backup / restore / disaster recovery

สร้าง consistent backup ของ PostgreSQL + storage:

```bash
make backup
```

Backup ถูกเก็บใต้ `PDFHUB_BACKUP_ROOT` (default `./backups`) พร้อม `manifest.env` และ `SHA256SUMS`; รองรับ local/NAS และ self-hosted S3-compatible storage

ตรวจ backup:

```bash
BACKUP=./backups/20260831T120000Z make backup-verify
```

Restore เป็น destructive operation และต้องยืนยัน explicit:

```bash
PDFHUB_RESTORE_CONFIRM=YES \
BACKUP=./backups/20260831T120000Z \
make restore
```

หลัง restore ระบบ flush เฉพาะ Valkey DB 0 ซึ่งเป็น ephemeral RQ state แล้วรัน migration และ readiness check เพื่อป้องกัน queued job เก่าชี้ metadata/storage คนละ snapshot

ทดสอบ disaster recovery แบบ isolated Compose project โดยไม่แตะ production project:

```bash
BACKUP=./backups/20260831T120000Z make dr-drill
```

ติดตั้ง daily backup timer แบบ systemd user service:

```bash
make install-backup
make backup-status
```

Default schedule 02:30 และ retention 14 วัน ปรับด้วย `PDFHUB_BACKUP_ON_CALENDAR`, `PDFHUB_BACKUP_ROOT`, `PDFHUB_BACKUP_RETENTION_DAYS`

## Load / release readiness

Load smoke แบบไม่เพิ่ม Python dependency:

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

Production gate ต้องมี backup ที่ตรวจได้และ deployment URL; default จะทำ DR drill ด้วย:

```bash
BACKUP=./backups/20260831T120000Z \
URL=https://pdf.example.org \
make release-readiness
```

## Production checklist

- ใช้ TLS/domain จริง และ `PDFHUB_SESSION_COOKIE_SECURE=true`
- สร้าง secret จริงด้วย `make secrets`; ห้ามใช้ example/default secret
- เปิด ClamAV fail-closed สำหรับไฟล์จากภายนอก
- จำกัด `PDFHUB_WEBHOOK_ALLOWED_HOSTS`
- คง management ports บน loopback/trusted management network
- เปิด backup timer และทดสอบ restore/DR เป็นระยะ
- ตรวจ Prometheus alerts และเชื่อม rule routing เข้าระบบแจ้งเตือนภายในที่เลือกใช้
- รัน `make release-readiness` ก่อน production release สำคัญ

## Phase completion

- Phase 1 — MVP / core processing
- Phase 2 — advanced PDF, quota, audit, administration
- Phase 3 — production / enterprise foundation (`0.3.0`)
- Phase 4 — image conversion, signed delivery, durable webhook (`0.4.0`; `0.4.1` maintenance)
- **Phase 5 — production maturity (`0.5.0`) — A/B/C implementation baseline complete**

## License

MIT สำหรับ source code ใน repository นี้ ดู `LICENSE`; dependencies ใช้ license ของ upstream
