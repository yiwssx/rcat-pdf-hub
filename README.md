# RCAT PDF Hub

ศูนย์กลางประมวลผล PDF แบบ **self-hosted / API-first** สำหรับให้หลายระบบใช้ PDF infrastructure ชุดเดียว โดยไม่ต้องติดตั้ง engine PDF ซ้ำในทุกโปรเจกต์

> Status: **0.3.0 — Phase 3 complete**
> Deployment target: Docker Compose บนเครื่องขององค์กร โดยรองรับ local volume, NAS และ self-hosted S3-compatible storage
> Cost policy: **zero-cost software/CI/CD** — ไม่พึ่ง paid runner, paid CI/CD หรือ paid cloud service

## ความสามารถปัจจุบัน

### PDF processing

- รวม PDF — qpdf
- แยก/เลือกหน้า — qpdf
- หมุนหน้า — qpdf
- บีบอัด — Ghostscript
- OCR ไทย + อังกฤษ — OCRmyPDF + Tesseract `tha+eng`
- PDF/A-2 — OCRmyPDF
- Word / Excel / PowerPoint / LibreOffice-compatible → PDF — Gotenberg
- Watermark ข้อความ รองรับภาษาไทย — pypdf + ReportLab + Noto Sans Thai
- เลขหน้าแบบกำหนด format/ตำแหน่งได้
- PDF Stamp — ใช้หน้าแรกของ PDF อีกไฟล์เป็น overlay
- Preview PDF → PNG — Poppler (`pdftoppm`) พร้อม cache

### Platform

- Upload / list / download file ผ่าน API
- Async job queue ผ่าน Valkey + RQ
- PostgreSQL metadata / job history
- API Key แยกแต่ละระบบ + scopes + revoke
- OIDC Authorization Code + PKCE SSO
- LDAP / Active Directory login พร้อม short-lived HttpOnly session
- Admin-group mapping และ human scopes
- Tenant/service isolation
- Per-service rate limit, daily job quota และ storage quota
- Signed webhook callback พร้อม HMAC และ hostname allowlist
- JSONL append-only audit trail
- Automatic retention cleanup worker
- Local / NAS / self-hosted S3-compatible storage
- ClamAV malware scanning แบบ fail-closed
- Prometheus metrics + OpenTelemetry OTLP tracing
- Paperless-ngx archive integration
- Alembic migrations พร้อม adoption จาก Phase 2 database
- `/healthz`, `/readyz` และ integration status endpoints
- Next.js Web Console + Admin
- Swagger/OpenAPI ที่ `/docs`
- Caddy reverse proxy
- Zero-cost local validation + local CI polling executor โดยไม่ใช้ GitHub-hosted runners

รายละเอียด Phase 3 ดูที่ `PHASE3.md`

## Architecture

```text
Browser / System A / System B / System C
                  |
                  v
             Caddy :8080
              /       \
             v         v
       Next.js UI   FastAPI
                       |
          +------------+-------------+
          |            |             |
          v            v             v
     PostgreSQL      Valkey       Storage
                       |        local/NAS/S3
                       v
                   RQ Worker
            +----------+-----------+
            |          |           |
            v          v           v
          qpdf     OCRmyPDF     Gotenberg
        pypdf/RL   Tesseract    LibreOffice
            |
            v
       processed PDF

Cleanup Worker ---> retention / temp cleanup
Worker ---------> signed webhooks
Optional -------> ClamAV / Prometheus / OTel / Paperless-ngx / SeaweedFS
```

Gotenberg, PostgreSQL, Valkey, ClamAV และ object storage ไม่ควร publish ตรงสู่ Internet ทุก request ภายนอกผ่าน PDF Hub API/Caddy ก่อน

## Quick start

ต้องมี Docker Engine + Docker Compose plugin แนะนำ RAM **8 GB** ถ้าจะใช้ OCR/Office พร้อมกันหลายงาน

```bash
cp .env.example .env
make secrets
```

นำ secret ที่ได้ไปแทนค่า placeholder ใน `.env` แล้วรัน:

```bash
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

`PDFHUB_ADMIN_API_KEY` เป็น bootstrap/break-glass key ที่มี scope `*` ควรใช้เฉพาะงานผู้ดูแลและไม่ฝังไว้ใน application

ระบบรองรับทั้ง machine-to-machine API key และ human login ผ่าน OIDC/LDAP การ map กลุ่มผู้ดูแล, scopes, quota และ service isolation ถูกบังคับใน API layer

ตัวอย่างสร้าง service key:

```bash
curl -X POST http://localhost:8080/api/v1/admin/api-keys \
  -H "X-API-Key: YOUR_BOOTSTRAP_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "student-system",
    "scopes": [
      "files:read", "files:write", "jobs:read",
      "pdf:merge", "pdf:split", "pdf:rotate", "pdf:compress",
      "pdf:ocr", "pdf:pdfa", "pdf:convert",
      "pdf:watermark", "pdf:page-number", "pdf:stamp"
    ],
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
| GET | `/api/v1/files/{id}` | `files:read` |
| GET | `/api/v1/files/{id}/download` | `files:read` |
| GET | `/api/v1/files/{id}/preview` | `files:read` |
| GET | `/api/v1/jobs` | `jobs:read` |
| GET | `/api/v1/jobs/{id}` | `jobs:read` |
| POST | `/api/v1/pdf/merge` | `pdf:merge` |
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
| GET | `/api/v1/admin/audit` | `admin:keys` |

รายละเอียด schema ที่แม่นที่สุดดูจาก Swagger `/docs`

## Storage

Default เป็น local storage และสามารถใช้ NAS ผ่าน `docker-compose.nas.yml`

สำหรับ S3-compatible storage โปรเจกต์บังคับให้กำหนด `PDFHUB_S3_ENDPOINT_URL` อย่างชัดเจน เพื่อให้ใช้เฉพาะ self-hosted endpoint และไม่ fallback ไปยัง paid cloud endpoint โดยไม่ตั้งใจ

Bundled development/small-site target:

```bash
make up-s3
```

จากนั้นตั้ง:

```env
PDFHUB_STORAGE_BACKEND=s3
PDFHUB_S3_ENDPOINT_URL=http://seaweedfs:8333
PDFHUB_S3_BUCKET=pdfhub
PDFHUB_S3_ACCESS_KEY=<random>
PDFHUB_S3_SECRET_KEY=<random>
PDFHUB_S3_AUTO_CREATE_BUCKET=true
```

## Security model

- Gotenberg และ data services ไม่เปิดตรงสู่ Internet
- API keys hash ด้วย SHA-256 + server-side pepper
- Bootstrap admin key อยู่ใน environment
- OIDC ใช้ state, nonce, PKCE และตรวจ issuer/audience/expiration/signature
- LDAP password ใช้เฉพาะ bind และไม่ถูกจัดเก็บ
- Service scopes + tenant isolation
- Upload size limit
- Rate limit + daily job quota + storage quota
- Webhook hostname allowlist + HMAC signature
- ClamAV scan upload และ processed output
- Worker resolve file path จาก database/storage abstraction เท่านั้น
- Audit log ไม่บันทึก plaintext API key / webhook secret
- Alembic migration ก่อน production API startup
- `/readyz` ตรวจ storage, Gotenberg และ ClamAV ตาม config

ก่อนเปิด Internet จริงให้ใช้ TLS/domain จริง, เปิด `PDFHUB_SESSION_COOKIE_SECURE=true`, ใช้ secret จาก `make secrets`, เปิด ClamAV fail-closed สำหรับไฟล์จากภายนอก และมี backup PostgreSQL + storage

## Optional self-hosted profiles

```bash
make up-security        # ClamAV
make up-observability   # Prometheus + OpenTelemetry Collector
make up-archive         # Paperless-ngx
make up-s3              # SeaweedFS
```

ทุก profile ใน repository สามารถ self-host ได้ด้วยซอฟต์แวร์ open-source/free ไม่มี paid cloud service เป็น requirement

## Free/open-source stack

- Caddy
- FastAPI / Python
- Next.js / React
- PostgreSQL
- Valkey / RQ
- Gotenberg / LibreOffice
- OCRmyPDF / Tesseract
- qpdf / Ghostscript
- pypdf / ReportLab
- Poppler
- SeaweedFS
- ClamAV
- Prometheus
- OpenTelemetry Collector
- Paperless-ngx

source code ของ RCAT PDF Hub ใช้ MIT License ส่วน dependency ใช้ license ของ upstream

## Development

Backend ใช้ Python **3.12**:

```bash
cd apps/api
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
PDFHUB_DATABASE_URL=sqlite+pysqlite:///:memory: \
PDFHUB_API_KEY_PEPPER=ci-test-pepper-change-me \
PDFHUB_ADMIN_API_KEY=pdfh_ci_admin_key_change_me \
PDFHUB_WEBHOOK_MASTER_SECRET=ci-webhook-master-secret-change-me \
python -m pytest -q
```

Frontend ใช้ Node **24**:

```bash
cd apps/web
npm install --package-lock=false
npm run dev
```

## Zero-cost validation

```bash
make validate-policy
make validate-backend
make validate-frontend
make validate-compose
make validate-runtime
# หรือทั้งหมด
make validate-free
```

Warnings และ deprecations ถือเป็น failure

Dependency/runtime policy:

- Dependabot ตรวจเฉพาะ direct npm dependencies ที่ประกาศใน `apps/web/package.json`
- Dependabot สร้างเฉพาะ patch update; minor/major ถูก ignore ตั้งแต่ต้นทาง
- ไม่อัปเดต transitive dependencies, `package-lock.json`, pip, Docker หรือ GitHub Actions อัตโนมัติ
- Python/Node base image และ Compose service images ถูก pin เป็น explicit release baseline; การอัปเดต infrastructure ต้องเป็น developer change โดยตั้งใจ
- `make validate-policy` ตรวจ policy เหล่านี้เพื่อป้องกัน regression

ตรวจ direct patch ก่อน merge:

```bash
BASE_REF=origin/main make validate-dependency
```

## Zero-cost automatic local CI

เครื่อง Linux ขององค์กรสามารถติดตั้ง local polling executor แบบ user service ได้โดยไม่ใช้ paid runner:

```bash
make install-local-ci
make local-ci-status
```

ตัว executor จะ:

1. fetch `origin/main`
2. รัน `make validate-free` เมื่อ `main` เปลี่ยน
3. ตรวจ PR ปกติที่อ้างอิง current `main` และรัน full `make validate-free` แบบ serialized
4. โพสต์ status `local-ci/validate-free` กลับ GitHub โดย **ไม่ auto-merge PR ปกติ**
5. ตรวจ Dependabot PR เฉพาะ direct `package.json` patch
6. รัน typecheck + production build แบบ warning-free
7. merge แบบ squash เฉพาะ Dependabot PR ที่ผ่าน policy และ validation จริง

ต้องติดตั้งและ login `gh` CLI บนเครื่อง executor ก่อน (`gh auth login`) เพื่อให้โพสต์ PR status และ merge Dependabot ได้ รายละเอียดดู `VALIDATION.md`

ถ้าต้องการหยุด:

```bash
make uninstall-local-ci
```

## Phase 3 completion

Phase 3 เสร็จแล้วใน 0.3.0: OIDC/LDAP, local/NAS/S3-compatible storage, horizontal RQ workers, ClamAV, Prometheus/OpenTelemetry, Paperless-ngx, Alembic migrations, zero-cost release policy และ local CI executor ถูก implement แล้ว

งานหลัง 0.3.0 เป็น enhancement ไม่ใช่ blocker ของ Phase 3 เช่น Image ↔ PDF batch tools, signed short-lived download URLs และ webhook delivery retry/dead-letter queue

## License

MIT สำหรับ source code ใน repository นี้ ดู `LICENSE`
