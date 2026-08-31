# RCAT PDF Hub

ศูนย์กลางประมวลผล PDF แบบ **self-hosted / API-first** สำหรับให้ผู้ใช้และระบบภายในองค์กรใช้ PDF infrastructure ชุดเดียวกัน โดยไม่ต้องติดตั้ง engine PDF ซ้ำในทุกโปรเจกต์

> Status: **0.5.1 — stabilization / correctness candidate**
> Deployment target: Docker Compose บนเครื่องขององค์กร รองรับ local volume, NAS และ self-hosted S3-compatible storage
> Cost policy: **zero-cost software/CI/CD** — ไม่พึ่ง paid runner, paid CI/CD หรือ paid cloud service

## ความสามารถหลัก

- รวม / แยก / เลือก / หมุน / บีบอัด PDF
- OCR ไทย + อังกฤษ และ PDF/A-2
- Word / Excel / PowerPoint / LibreOffice-compatible → PDF
- Watermark ภาษาไทย, เลขหน้า และ PDF stamp
- Preview PDF → PNG
- JPEG / PNG / WebP / TIFF / BMP หลายไฟล์ → PDF
- PDF → PNG/JPEG หลายหน้าเป็น ZIP
- Signed short-lived download URL
- Paperless-ngx archive integration
- PostgreSQL + Valkey/RQ + Caddy + local/NAS/self-hosted S3
- Backup/restore/DR drill, Prometheus/Alertmanager, load test และ Local CI

## Authentication model

RCAT PDF Hub แยก **human login** ออกจาก **machine credential** ชัดเจน:

- **Local Development:** local admin 1 บัญชีจาก `.env` เพื่อทดสอบระบบโดยไม่ต้องพึ่ง Google/LDAP
- **Production Human Login:** OIDC/SSO ขององค์กร (เป้าหมายคือบัญชี `@rcat.ac.th`)
- **Service API Key (`pdfh_...`):** สำหรับระบบต่อระบบเท่านั้น สร้างและบริหารจากหน้า Admin
- **Bootstrap Admin Key:** break-glass/initial administration เท่านั้น ไม่ใช่ login ประจำวัน

Local login ถูกปิดโดย default และ `scripts/check-production-env.py` จะปฏิเสธ production readiness หาก `PDFHUB_LOCAL_AUTH_ENABLED=true`

## First local run — วิธีแนะนำ

โปรเจกต์ 0.5.1 มี workflow สำหรับเครื่องที่ยังไม่เคยรัน RCAT PDF Hub มาก่อน:

```bash
git checkout stabilization/0.5.1-correctness
bash scripts/first-local.sh
```

ต้องมี Python **3.12**, Node **24**, Docker Engine + Compose plugin, GitHub CLI (`gh`) และ RAM แนะนำ **8 GB** ขึ้นไป

`first-local.sh` จะ:

1. สร้าง `.env` และ random secrets
2. เปิด `PDFHUB_LOCAL_AUTH_ENABLED=true`
3. สร้าง local username `admin` และ random password
4. resolve dependency lockfiles จริง
5. รัน repository validation
6. build/start Docker Compose stack
7. ตรวจ `/healthz` + `/readyz` + real PDF workload
8. สร้าง/verify backup และรัน DR drill
9. ติดตั้ง/รัน institution-owned Local CI

หลังสำเร็จ เปิด:

```text
http://127.0.0.1:8080
```

Username:

```text
admin
```

Password อ่านจาก:

```bash
grep '^PDFHUB_LOCAL_ADMIN_PASSWORD=' .env
```

`.env` ถูกตั้ง permission `600` เมื่อ script เป็นผู้สร้าง

## Manual local start

ถ้ามี `.env` พร้อมแล้ว:

```bash
docker compose up -d --build --wait
```

URLs:

- Web Console: `http://localhost:8080`
- Swagger: `http://localhost:8080/docs`
- Health: `http://localhost:8080/healthz`
- Readiness: `http://localhost:8080/readyz`

## UI

หน้าหลักแบ่งเครื่องมือ 14 รายการเป็น 4 กลุ่มเพื่อหาได้เร็วขึ้น:

- **จัดการหน้าและเอกสาร** — OCR, Merge, Organize, Split, Compress
- **แปลงไฟล์** — PDF→Image, Image→PDF, PDF/A, Office→PDF
- **ปรับแต่งเอกสาร** — Watermark, Page number, Stamp
- **แชร์และจัดเก็บ** — Signed URL, Paperless archive

Desktop ใช้ tool cards หลายคอลัมน์ ส่วน Mobile ย่อเป็น responsive grid + bottom navigation

## Service API Keys

`PDFHUB_ADMIN_API_KEY` เป็น bootstrap/break-glass key ที่มี scope `*` ควรใช้เฉพาะ bootstrap/recovery และไม่ฝังใน frontend หรือ application ภายนอก

ตัวอย่างสร้าง Service API Key:

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

plaintext key ถูกคืนครั้งเดียว จากนั้นฐานข้อมูลเก็บเฉพาะ hash ที่ผสม server-side pepper

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

Cleanup Worker ------> retention / stale-job reconciliation
Webhook Dispatcher --> retry / dead-letter delivery
Optional ------------> ClamAV / Prometheus / Alertmanager / OTel / Paperless / SeaweedFS
```

## Validation

```bash
make validate-policy
make validate-ops
make validate-backend
make validate-frontend
make validate-e2e
make validate-compose
make validate-runtime
make validate-free
```

Production readiness:

```bash
BACKUP=/path/to/verified-backup \
URL=https://your-production-host \
make release-readiness
```

Production gate ตรวจอย่างน้อย:

- HTTPS + Secure cookie
- local authentication ต้องปิด
- secret placeholders ต้องไม่มี
- management ports ต้องไม่ bind ทุก interface
- backup ต้องเป็น quiesced snapshot
- DR drill
- readiness/load test
- real PDF transaction workload
- Local CI status

## Operational commands

```bash
make ps
make logs
make backup
make backup-verify
make dr-drill
make local-ci-doctor
```

รายละเอียด baseline ก่อนหน้าอยู่ใน `PHASE3.md`, `PHASE4.md`, `PHASE5.md`, `VALIDATION.md` และ `CHANGELOG.md`
