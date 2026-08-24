# RCAT PDF Hub

ศูนย์กลางประมวลผล PDF แบบ **self-hosted / API-first** สำหรับให้หลายระบบใช้ PDF infrastructure ชุดเดียว โดยไม่ต้องติดตั้ง engine PDF ซ้ำในทุกโปรเจกต์

> Status: **0.2.0 — Phase 2**
> Deployment target: Docker Compose เครื่องเดียวก่อน และสามารถแยก worker/storage ภายหลัง

## ความสามารถปัจจุบัน

### PDF processing

- รวม PDF — qpdf
- แยก/เลือกหน้า — qpdf
- หมุนหน้า — qpdf
- บีบอัด — Ghostscript
- OCR ไทย + อังกฤษ — OCRmyPDF + Tesseract `tha+eng`
- PDF/A-2 — OCRmyPDF
- Word / Excel / PowerPoint / LibreOffice-compatible → PDF — Gotenberg
- **Watermark ข้อความ รองรับภาษาไทย** — pypdf + ReportLab + Noto Sans Thai
- **เลขหน้าแบบกำหนด format/ตำแหน่งได้**
- **PDF Stamp** — นำหน้าแรกของ PDF อีกไฟล์มา overlay ตามตำแหน่ง/scale
- **Preview PDF → PNG** — Poppler (`pdftoppm`) พร้อม cache

### Platform

- Upload / list / download file ผ่าน API
- Async job queue ผ่าน **Valkey + RQ**
- PostgreSQL metadata / job history
- API Key แยกแต่ละระบบ + scopes + revoke
- Tenant/service isolation: service อ่านและประมวลผลได้เฉพาะไฟล์ของตัวเอง
- **Per-service rate limit, daily job quota และ storage quota**
- **Webhook callback เมื่อ job completed/failed** พร้อม HMAC signature และ host allowlist
- **Audit trail แบบ JSONL append-only** สำหรับ upload/download/job/admin/webhook/cleanup
- **Automatic retention cleanup worker**
- Next.js Web Console สำหรับ tools + Admin
- Swagger/OpenAPI ที่ `/docs`
- Caddy reverse proxy
- Zero-cost local validation: backend tests + frontend build + Compose/runtime checks โดยไม่ใช้ GitHub-hosted runners

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
     PostgreSQL      Valkey      Shared Volume
                       |             |
                       v             +--> previews/audit
                   RQ Worker
            +----------+-----------+
            |          |           v
            v          v        Gotenberg
          qpdf     OCRmyPDF     LibreOffice
        pypdf/RL   Tesseract
            |
            v
       processed PDF

     Cleanup Worker ---> retention / temp cleanup
     Worker ---------> signed webhooks (allowlisted hosts only)
```

Gotenberg ไม่ publish port ออก host โดยตรง ทุก request ผ่าน PDF Hub API ก่อน

## Quick start

ต้องมี Docker Engine + Docker Compose plugin แนะนำ RAM **8 GB** ถ้าจะใช้ OCR/Office พร้อมกันหลายงาน

```bash
cp .env.example .env
make secrets
```

นำ secret ที่ได้ไปแทน `CHANGE_ME...` ใน `.env` แล้วรัน:

```bash
make config
make up
```

เปิด:

- Web Console: `http://SERVER_IP:8080`
- Swagger: `http://SERVER_IP:8080/docs`
- Health: `http://SERVER_IP:8080/healthz`

```bash
make ps
make logs
```

## Authentication / Service isolation

`PDFHUB_ADMIN_API_KEY` เป็น bootstrap/break-glass key ที่มี scope `*` ควรใช้เฉพาะงานผู้ดูแลและไม่ฝังไว้ใน application

สร้าง key สำหรับระบบหนึ่งผ่าน Web Admin หรือ API:

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

plaintext API key (`pdfh_...`) ถูกคืน **ครั้งเดียว** จากนั้น DB เก็บเฉพาะ hash ที่ผสม server-side pepper

## Workflow หลัก

### Upload

```bash
curl -X POST http://localhost:8080/api/v1/files \
  -H "X-API-Key: SERVICE_KEY" \
  -F "file=@scan.pdf"
```

### OCR ไทย + อังกฤษ

```bash
curl -X POST http://localhost:8080/api/v1/pdf/ocr \
  -H "X-API-Key: SERVICE_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "file_id": "FILE_ID",
    "languages": "tha+eng",
    "deskew": true,
    "rotate_pages": true
  }'
```

API ตอบ `202 Accepted` พร้อม `job.id`

### Poll job

```bash
curl http://localhost:8080/api/v1/jobs/JOB_ID \
  -H "X-API-Key: SERVICE_KEY"
```

เมื่อ `status=completed` จะมี `output_file_id`

### Download

```bash
curl -L http://localhost:8080/api/v1/files/OUTPUT_FILE_ID/download \
  -H "X-API-Key: SERVICE_KEY" \
  -o result.pdf
```

## Phase 2 API

| Method | Endpoint | Scope |
|---|---|---|
| GET / POST | `/api/v1/files` | `files:read` / `files:write` |
| GET | `/api/v1/files/{id}` | `files:read` |
| GET | `/api/v1/files/{id}/download` | `files:read` |
| GET | `/api/v1/files/{id}/preview?page=1&width=720` | `files:read` |
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
| GET / POST / DELETE | `/api/v1/admin/api-keys...` | `admin:keys` |
| GET / PUT | `/api/v1/admin/service-policies...` | `admin:keys` |
| GET | `/api/v1/admin/audit` | `admin:keys` |

รายละเอียด schema ที่แม่นที่สุดดูจาก Swagger `/docs`

## Watermark

```json
{
  "file_id": "FILE_ID",
  "text": "เอกสารภายใน",
  "font_size": 48,
  "opacity": 0.18,
  "rotation": 45,
  "position": "center",
  "margin": 36
}
```

ตำแหน่งที่รองรับ: `center`, `top-left`, `top-center`, `top-right`, `bottom-left`, `bottom-center`, `bottom-right`

## Page numbers

```json
{
  "file_id": "FILE_ID",
  "format": "หน้า {page} / {total}",
  "start_number": 1,
  "font_size": 10,
  "position": "bottom-center",
  "margin": 24
}
```

## PDF Stamp

อัปโหลด PDF สำหรับใช้เป็น stamp ก่อน แล้วส่ง:

```json
{
  "file_id": "TARGET_PDF_ID",
  "stamp_file_id": "STAMP_PDF_ID",
  "position": "bottom-right",
  "scale": 0.2,
  "margin": 24
}
```

ใช้หน้าแรกของ `stamp_file_id` เป็น overlay บนทุกหน้าของไฟล์เป้าหมาย

## Preview

Preview ใช้ Poppler สร้าง PNG และ cache ใน `/data/previews/`

```bash
curl -H "X-API-Key: SERVICE_KEY" \
  "http://localhost:8080/api/v1/files/FILE_ID/preview?page=1&width=900" \
  -o preview.png
```

## Service quota / rate limit

แต่ละ service มี policy:

- `rate_limit_per_minute` — จำนวน authenticated requests ต่อนาที (`0` = unlimited)
- `daily_job_limit` — จำนวน PDF jobs ต่อวัน UTC (`0` = unlimited)
- `max_storage_mb` — active file metadata ก่อน expiry (`0` = unlimited)
- `webhook_url` — callback ของ service

ค่า default มาจาก `.env` และแก้ราย service ได้จากหน้า Admin

## Webhooks

เพื่อป้องกัน SSRF, outbound webhook **ปิดเป็นค่าเริ่มต้น** จนกว่าจะกำหนด allowlist:

```env
PDFHUB_WEBHOOK_ALLOWED_HOSTS=sis.internal.example.org,*.internal.example.org
PDFHUB_WEBHOOK_MASTER_SECRET=<random secret>
```

เมื่อสร้าง/แก้ policy ให้กำหนด `webhook_url` ที่ hostname อยู่ใน allowlist

PDF Hub ส่ง event เมื่อ job `completed` หรือ `failed` พร้อม headers:

```text
X-PDFHub-Event: job.completed
X-PDFHub-Timestamp: 1787...
X-PDFHub-Signature: sha256=<hex>
```

Signing secret ของแต่ละ service ถูก derive จาก master secret + service name; Admin สามารถอ่านได้ที่:

```text
GET /api/v1/admin/service-policies/{service_name}/webhook-secret
```

วิธี verify signature:

```text
HMAC-SHA256(service_webhook_secret, timestamp + "." + raw_request_body)
```

ควรจำกัด egress network ของ worker เพิ่มอีกชั้นใน production

## Retention / Cleanup

`cleanup` container รันตาม `PDFHUB_CLEANUP_INTERVAL_SECONDS` (default 900 วินาที)

- ลบ bytes ของไฟล์ที่ `expires_at` หมดอายุ
- ลบ preview cache ของไฟล์นั้น
- ลบ temporary file ที่เก่ากว่า `PDFHUB_CLEANUP_TEMPORARY_HOURS`
- **เก็บ metadata/job history ใน PostgreSQL ไว้** เพื่อ audit/reference

สั่ง cleanup ครั้งเดียว:

```bash
make cleanup
```

## Audit trail

เก็บ JSONL ที่:

```text
/data/audit/audit.jsonl
```

ครอบคลุม event สำคัญ เช่น:

- file uploaded / downloaded / previewed / quota rejected
- job queued / started / completed / failed
- API key created / revoked
- service policy updated
- webhook delivered / failed / blocked
- retention cleanup

ดูผ่าน Admin UI หรือ `GET /api/v1/admin/audit`

## Storage

```text
/data/
├── originals/
├── processed/
├── temporary/
├── previews/
└── audit/
```

PostgreSQL เก็บ metadata/hash/job state ไม่เก็บ binary PDF

## Security model

- Gotenberg ไม่เปิดตรงสู่ Internet
- API keys hash ด้วย SHA-256 + server-side pepper
- Bootstrap admin key อยู่ใน environment
- Service scopes แยก operation
- Service isolation ตรวจ `source_system` ทุก file/job path
- ไม่ส่ง API key ผ่าน query string
- จำกัด upload size
- Rate limit + daily job quota + storage quota
- Webhook URL ต้องผ่าน hostname allowlist และไม่มี URL credentials
- Webhook มี HMAC signature แยก secret ต่อ service
- Worker resolve file path จาก DB เท่านั้น ไม่รับ filesystem path จาก client
- Caddy ใส่ security headers ขั้นต้น
- Audit log ไม่บันทึก plaintext API key / webhook secret

ก่อนเปิด Internet จริงยังควรเพิ่ม TLS/domain จริง, WAF/rate limit ที่ edge, ClamAV, SSO/OIDC และ backup policy

## Free/open-source stack

source code ของ RCAT PDF Hub ใช้ MIT License ส่วน dependency ใช้ license ของ upstream:

- Gotenberg — MIT
- OCRmyPDF — MPL-2.0
- Tesseract — Apache-2.0
- qpdf — Apache-2.0
- pypdf — BSD-3-Clause
- ReportLab — BSD-style
- PostgreSQL — PostgreSQL License
- Valkey — BSD-3-Clause
- FastAPI — MIT
- Next.js / React — MIT

CI/validation ใช้เครื่องที่องค์กรมีอยู่แล้วและเครื่องมือ open-source เท่านั้น ไม่มี paid runner หรือ paid CI fallback

## Development

Backend:

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

Frontend:

```bash
cd apps/web
npm install --package-lock=false
npm run dev
```

Zero-cost validation:

```bash
make validate-policy
make validate-free
```

ตรวจ direct dependency patch ก่อน merge:

```bash
BASE_REF=origin/main make validate-dependency
```

## Roadmap

### 0.2.x

- Image → PDF / PDF → image batch tools
- Signed short-lived download URLs
- Webhook delivery queue / dead-letter retry
- Database migrations (Alembic) before schema evolves beyond additive tables

### Phase 3

- SSO/OIDC/LDAP สำหรับ human users
- S3/MinIO/NAS storage backend
- Horizontal workers
- ClamAV malware scanning
- Prometheus/OpenTelemetry observability
- Paperless-ngx archive/DMS integration

## License

MIT สำหรับ source code ใน repository นี้ ดู `LICENSE`
