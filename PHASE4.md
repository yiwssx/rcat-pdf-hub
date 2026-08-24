# Phase 4 — Secure Delivery & Media Conversion

RCAT PDF Hub **0.4.0** is the completed Phase 4 feature baseline. It builds on the completed Phase 3 platform and adds secure short-lived file delivery, batch Image ↔ PDF conversion, and durable webhook delivery with retry and dead-letter recovery while preserving the zero-cost/self-hosted operating model.

## Maintenance release 0.4.1

Phase 4 remains feature-complete. Version **0.4.1** is a security/validation maintenance release, not a new feature phase.

- Pillow is upgraded from 11.3.0 to the reviewed secure 12.3.0 baseline.
- Release validation requires an exact Pillow pin on the reviewed 12.x line at or above 12.3.0 and below 13.0.0; crossing major versions remains an explicit developer decision.
- `validate-free.sh` delegates policy checks to `scripts/validate-release-policy.py` so release/dependency rules have one source of truth.
- Dependabot version-update automation remains direct npm patch-only.
- Security PRs opened outside that lane, including pip/security updates, receive full `make validate-free` validation on institution-owned hardware and are never auto-merged.

## Delivered capabilities

- Batch JPEG / PNG / WebP / TIFF / BMP → PDF conversion.
- Configurable image page size (`auto`, A4, Letter), fit mode, margin and DPI.
- PDF → PNG/JPEG page rasterization with selected page ranges.
- PDF-to-image jobs return a ZIP file so one job still maps to one managed `FileRecord`.
- Stateless HMAC-signed short-lived download URLs bound to file ID, owning service and expiry.
- Configurable default and maximum signed-download TTL.
- Dedicated download-signing secret that can be rotated independently from API/session secrets.
- Persistent webhook delivery records in PostgreSQL.
- Exponential webhook retry with configurable attempt count and backoff ceiling.
- Dead-letter state after retry exhaustion.
- Dedicated webhook dispatcher service that survives API/RQ worker restarts.
- Admin API for inspecting webhook deliveries and replaying dead-letter deliveries.
- Delivery ID and attempt number headers on webhook requests.
- Phase 4 Alembic migration and regression tests.

## Image → PDF

Endpoint:

```text
POST /api/v1/pdf/images-to-pdf
```

Scope:

```text
pdf:image-to-pdf
```

Example request:

```json
{
  "file_ids": ["IMAGE_FILE_ID_1", "IMAGE_FILE_ID_2"],
  "page_size": "a4",
  "fit": "contain",
  "margin": 18,
  "dpi": 150
}
```

Input files must be owned by the calling service unless the caller has `*` scope. Accepted MIME types are JPEG, PNG, WebP, TIFF and BMP. Every input image becomes one PDF page in the supplied order.

## PDF → images

Endpoint:

```text
POST /api/v1/pdf/pdf-to-images
```

Scope:

```text
pdf:pdf-to-image
```

Example request:

```json
{
  "file_id": "PDF_FILE_ID",
  "format": "png",
  "dpi": 150,
  "first_page": 1,
  "last_page": 5
}
```

The output is a managed `application/zip` file containing deterministic names such as `page-0001.png`. Retention, storage quota, malware scanning, tenant isolation, audit logging and signed downloads apply to the ZIP exactly as they do to PDF outputs. PDF-to-image jobs are capped by `PDFHUB_PDF_TO_IMAGE_MAX_PAGES` (default 200 pages per job).

## Signed short-lived downloads

Authenticated callers with `files:read` can issue a signed URL:

```text
POST /api/v1/files/{file_id}/signed-download?ttl_seconds=300
```

The response contains:

```json
{
  "file_id": "...",
  "url": "https://pdf.example.org/api/v1/files/.../signed-download?expires=...&token=...",
  "expires_at": "..."
}
```

The resulting GET URL does not require an API key or session cookie. The HMAC binds:

1. file ID,
2. owning service,
3. absolute expiry.

The server rejects expired URLs, tampered tokens and expiries beyond `PDFHUB_SIGNED_DOWNLOAD_MAX_TTL_SECONDS`.

Configuration:

```env
PDFHUB_DOWNLOAD_SIGNING_SECRET=<random-secret-at-least-32-bytes>
PDFHUB_SIGNED_DOWNLOAD_DEFAULT_TTL_SECONDS=300
PDFHUB_SIGNED_DOWNLOAD_MAX_TTL_SECONDS=3600
```

Rotate `PDFHUB_DOWNLOAD_SIGNING_SECRET` to invalidate all outstanding signed URLs immediately.

## Durable webhook delivery

Phase 3 delivered signed webhooks but retry state lived only inside the worker call. Phase 4 persists every delivery in `webhook_deliveries` and moves outbound delivery to the dedicated `webhook` service.

State machine:

```text
queued -> retrying -> delivered
                    -> dead

dead --admin replay--> queued
```

Default retry policy:

- maximum attempts: 6
- initial delay: 5 seconds
- exponential backoff
- maximum delay: 900 seconds

Configuration:

```env
PDFHUB_WEBHOOK_TIMEOUT_SECONDS=10
PDFHUB_WEBHOOK_MAX_ATTEMPTS=6
PDFHUB_WEBHOOK_RETRY_INITIAL_SECONDS=5
PDFHUB_WEBHOOK_RETRY_MAX_SECONDS=900
PDFHUB_WEBHOOK_DISPATCH_INTERVAL_SECONDS=2
PDFHUB_WEBHOOK_DISPATCH_BATCH_SIZE=50
```

Webhook requests include:

```text
X-PDFHub-Event
X-PDFHub-Delivery
X-PDFHub-Attempt
X-PDFHub-Timestamp
X-PDFHub-Signature
```

The signature remains HMAC-SHA256 over `timestamp + "." + raw_body` with the service-specific secret derived from `PDFHUB_WEBHOOK_MASTER_SECRET`.

## Dead-letter administration

List deliveries:

```text
GET /api/v1/admin/webhook-deliveries
GET /api/v1/admin/webhook-deliveries?status=dead
GET /api/v1/admin/webhook-deliveries?service_name=student-system
```

Replay a dead delivery:

```text
POST /api/v1/admin/webhook-deliveries/{delivery_id}/retry
```

These endpoints require `admin:keys`.

## Database migration

Phase 4 adds:

```text
0003_phase4_webhook_deliveries
```

Production startup continues to run Alembic before the API becomes healthy. Back up PostgreSQL and binary storage together before upgrading.

## Deployment

Generate all secrets, including the download-signing secret:

```bash
make secrets
```

Then:

```bash
make config
make up
```

The default Compose stack includes the dedicated `webhook` dispatcher service. No external queue, paid webhook provider or paid scheduler is required.

## Validation

```bash
make validate-policy
make validate-backend
make validate-frontend
make validate-compose
make validate-runtime
# or
make validate-free
```

Phase 4 regression coverage includes signed-token binding/TTL, multi-image PDF generation, PDF page rasterization/ZIP output, and webhook retry/dead-letter/requeue lifecycle. The 0.4.1 maintenance gate also verifies the reviewed Pillow security floor and the security-PR full-validation lane.

## Zero-cost rule

Phase 4 preserves the project rule that normal operation and validation must not require paid runners, paid CI/CD, paid cloud storage, paid monitoring, paid webhook delivery or paid build services. Deployment remains targeted at institution-owned hardware with free/open-source software.

## Completion status

RCAT PDF Hub **0.4.0 is the completed Phase 4 feature baseline**. Version **0.4.1** is its security-maintenance release. New feature work after this baseline should be treated as Phase 5/enhancement work rather than a Phase 4 blocker.
