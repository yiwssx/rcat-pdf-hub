# PDF Hub

ศูนย์กลางประมวลผล PDF แบบ self-hosted สำหรับให้งานเว็บ ระบบทะเบียน ระบบเอกสาร หรือ service อื่น ๆ ใช้ PDF infrastructure ชุดเดียวผ่าน REST API

> Status: **MVP 0.1.0** — ออกแบบให้รันบน Docker Compose เครื่องเดียวก่อน และแยก worker เพิ่มได้ภายหลัง

## สิ่งที่มีแล้ว

- Upload/download file แบบมี API key
- API key แยกตามระบบ พร้อม scope และ revoke
- Isolation: service key ประมวลผล/อ่านได้เฉพาะไฟล์ที่ service นั้นอัปโหลด (bootstrap admin เห็นทั้งหมด)
- Async job queue ผ่าน Valkey + RQ
- Merge PDF — qpdf
- Split/page selection — qpdf
- Rotate — qpdf
- Compress — Ghostscript
- OCR ไทย + อังกฤษ — OCRmyPDF + Tesseract (`tha+eng`)
- PDF/A-2 — OCRmyPDF
- Word/Excel/PowerPoint/LibreOffice-compatible document → PDF — Gotenberg
- PostgreSQL metadata/job history
- Next.js web console เบื้องต้น
- OpenAPI/Swagger ที่ `/docs`
- Reverse proxy ผ่าน Caddy
- GitHub Actions CI เบื้องต้น

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
             +---------+----------+
             |                    |
             v                    v
        PostgreSQL              Valkey
                                  |
                                  v
                              RQ Worker
                         +--------+--------+
                         |        |        |
                         v        v        v
                       qpdf   OCRmyPDF  Gotenberg
                         |     Tesseract   LibreOffice
                         +--------+--------+
                                  |
                                  v
                            Shared PDF Volume
```

Gotenberg ไม่ถูก publish port ออก host โดยตรง; request ต้องผ่าน PDF Hub API ก่อน

## Quick start

ต้องมี Docker Engine + Docker Compose plugin และควรมี RAM อย่างน้อย 4 GB (แนะนำ 8 GB ถ้า OCR/Office พร้อมกันหลายงาน)

```bash
cp .env.example .env
make secrets
```

นำค่าที่ `make secrets` สร้างไปแทน `CHANGE_ME...` ใน `.env` แล้วรัน

```bash
make up
```

เปิด:

- Web UI: `http://SERVER_IP:8080`
- Swagger/OpenAPI: `http://SERVER_IP:8080/docs`
- Health: `http://SERVER_IP:8080/healthz`

ตรวจ container:

```bash
make ps
make logs
```

## Bootstrap admin key

`PDFHUB_ADMIN_API_KEY` เป็น break-glass/bootstrap key มีสิทธิ์ `*` ทุกอย่าง ควรใช้เฉพาะสร้าง/revoke service key แล้วเก็บแยกจาก application

สร้าง API key สำหรับระบบทะเบียน:

```bash
curl -X POST http://localhost:8080/api/v1/admin/api-keys \
  -H "X-API-Key: YOUR_BOOTSTRAP_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "student-system",
    "scopes": [
      "files:read",
      "files:write",
      "jobs:read",
      "pdf:merge",
      "pdf:split",
      "pdf:rotate",
      "pdf:compress",
      "pdf:ocr",
      "pdf:pdfa",
      "pdf:convert"
    ]
  }'
```

API จะคืน plaintext key **ครั้งเดียว** เช่น `pdfh_...` จากนั้น database เก็บเฉพาะ hash

ดู key ทั้งหมด:

```bash
curl http://localhost:8080/api/v1/admin/api-keys \
  -H "X-API-Key: YOUR_BOOTSTRAP_ADMIN_KEY"
```

Revoke:

```bash
curl -X DELETE http://localhost:8080/api/v1/admin/api-keys/KEY_ID \
  -H "X-API-Key: YOUR_BOOTSTRAP_ADMIN_KEY"
```

## Workflow ตัวอย่าง

### 1. Upload

```bash
curl -X POST http://localhost:8080/api/v1/files \
  -H "X-API-Key: SERVICE_KEY" \
  -F "file=@scan.pdf"
```

เก็บ `id` ที่ได้ เช่น `FILE_ID`

### 2. OCR ไทย + อังกฤษ

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

### 3. Poll job

```bash
curl http://localhost:8080/api/v1/jobs/JOB_ID \
  -H "X-API-Key: SERVICE_KEY"
```

เมื่อ `status=completed` จะมี `output_file_id`

### 4. Download

```bash
curl -L http://localhost:8080/api/v1/files/OUTPUT_FILE_ID/download \
  -H "X-API-Key: SERVICE_KEY" \
  -o result.pdf
```

## API ที่มีใน MVP

| Method | Endpoint | Scope |
|---|---|---|
| POST | `/api/v1/files` | `files:write` |
| GET | `/api/v1/files/{id}` | `files:read` |
| GET | `/api/v1/files/{id}/download` | `files:read` |
| GET | `/api/v1/jobs` | `jobs:read` |
| GET | `/api/v1/jobs/{id}` | `jobs:read` |
| POST | `/api/v1/pdf/merge` | `pdf:merge` |
| POST | `/api/v1/pdf/split` | `pdf:split` |
| POST | `/api/v1/pdf/rotate` | `pdf:rotate` |
| POST | `/api/v1/pdf/compress` | `pdf:compress` |
| POST | `/api/v1/pdf/ocr` | `pdf:ocr` |
| POST | `/api/v1/pdf/pdfa` | `pdf:pdfa` |
| POST | `/api/v1/pdf/office-to-pdf` | `pdf:convert` |
| GET/POST/DELETE | `/api/v1/admin/api-keys...` | `admin:keys` |

## Merge

```json
{
  "file_ids": ["FILE_ID_1", "FILE_ID_2"]
}
```

## Split / เลือกหน้า

`pages` ใช้รูปแบบ qpdf เช่น `1-3,5,8-10`

```json
{
  "file_id": "FILE_ID",
  "pages": "1-3,5"
}
```

## Rotate

```json
{
  "file_id": "FILE_ID",
  "degrees": 90,
  "pages": "1-z"
}
```

## Office → PDF

อัปโหลด `.docx`, `.xlsx`, `.pptx`, `.odt` ฯลฯ ผ่าน `/files` ก่อน แล้วส่ง

```json
{
  "file_id": "FILE_ID"
}
```

ไปที่ `/api/v1/pdf/office-to-pdf`

## Storage

ไฟล์จริงอยู่ใน Docker volume `pdf_data`

```text
/data/
├── originals/
├── processed/
└── temporary/
```

PostgreSQL เก็บ metadata/hash/job status ไม่เก็บ binary PDF ลง database

`PDFHUB_RETENTION_HOURS` ถูกบันทึกเป็น expiry metadata แล้ว แต่ **MVP นี้ยังไม่ได้เปิด scheduled cleanup** จึงยังไม่ลบไฟล์อัตโนมัติ การทำ retention worker เป็นงาน Phase 2

## Security model

- ไม่เปิด Gotenberg สู่ Internet โดยตรง
- API key ถูก hash ด้วย SHA-256 + server-side pepper ก่อนเก็บ
- Bootstrap key มาจาก environment เท่านั้น
- Service key มี scopes แยก operation
- Service isolation ตรวจ `source_system` ก่อนอ่านหรือส่งไฟล์เข้า job
- ไม่ส่ง API key ผ่าน query string
- จำกัด upload ด้วย `PDFHUB_MAX_UPLOAD_MB`
- Worker รับเฉพาะ file path ที่ resolve จาก database ไม่รับ arbitrary filesystem path จาก client
- Caddy ใส่ security headers ขั้นต้น

ก่อนเปิด Internet จริง ควรเพิ่ม TLS, rate limit, malware scanning, audit log แบบ append-only และ SSO/OIDC สำหรับ human users

## Free/open-source stack

ตัว project code นี้ออกภายใต้ MIT License ส่วน dependency แต่ละตัวใช้ license ของ upstream เอง ตัวหลักที่ตั้งใจเลือกเพื่อหลีกเลี่ยง commercial lock-in ได้แก่:

- Gotenberg — MIT
- OCRmyPDF — MPL-2.0
- Tesseract — Apache-2.0
- qpdf — Apache-2.0
- PostgreSQL — PostgreSQL License
- Valkey — BSD-3-Clause
- FastAPI — MIT
- Next.js / React — MIT

ไม่ได้ bundle source code ของ dependencies เหล่านี้เข้ามาใน repository นี้; Docker/package manager ดาวน์โหลดจาก upstream

## Development

Backend:

```bash
cd apps/api
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python -m pytest -q
```

Frontend:

```bash
cd apps/web
npm install
npm run dev
```

## Roadmap

### Phase 2

- Watermark / stamp / page number
- Image ↔ PDF
- Preview thumbnails
- Signed short-lived download URLs
- Automatic retention cleanup
- Web UI สำหรับ split/rotate/Office conversion/API-key admin
- Webhook callback เมื่อ job เสร็จ
- Per-service quota/rate limit
- Audit trail

### Phase 3

- SSO/OIDC/LDAP สำหรับผู้ใช้บุคคล
- S3/MinIO/NAS storage backend
- Horizontal workers
- Malware scan (ClamAV)
- Observability (Prometheus/OpenTelemetry)
- Paperless-ngx integration สำหรับ archive/DMS

## License

MIT สำหรับ source code ใน repository นี้ ดู `LICENSE`
