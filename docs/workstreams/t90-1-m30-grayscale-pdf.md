# T90-1 / M30 — Grayscale PDF (conservative bounded scope)

Tracker #225 / #172. Independent release acceptance #262.

## Behavior

A new staged tool accepts **one verified PDF** owned by the submitting
principal and produces a new PDF whose page content is converted to gray
through the existing Ghostscript `pdfwrite` engine
(`-dSAFER -sColorConversionStrategy=Gray -dProcessColorModel=/DeviceGray`).
This is grayscale, not black/white thresholding, compression or redaction.

The dedicated `POST /api/v1/pdf/grayscale-pdf` accepts only
`{"file_id": "<opaque id>"}` and requires the independent
`pdf:grayscale` scope. API and Worker both require exact ownership,
non-expired PDF MIME/name, valid on-disk signature, no extra parameters and
16 MiB max source size. Do not allow wildcard scope to override tenant
ownership for this staged tool.

The narrow native engine allows up to 200 pages, each 10–2880 PDF points on
either side, and 64 MiB output. Before atomic publication the output is
reopened as a genuine unencrypted PDF, with original page count,
MediaBox, CropBox and rotation checked. Source remains unchanged. Normal
artifact malware scan, quota, tenant binding, retention, transaction,
cancellation and storage-recovery behavior are inherited. Grayscale
results are not automatically sent to Paperless.

## Fail-closed scope

Encrypted, corrupt or malformed PDFs, existing outputs, signed PDFs, PDF
forms and annotated PDFs are rejected. Ghostscript pdfwrite can rewrite
internal objects or normalize colors and typography; it does not preserve
cryptographic signatures, source object identity, PDF/A certification,
interactivity, precise ICC/CMYK colorspace, PDF transparency fidelity or
every Thai font's rendering. Source documents needing these guarantees
require independent approval and should not be processed by this subset.

Subprocess invocation is a fixed Ghostscript argument array (no shell),
with the existing GS safety flag and 600-second timeout. Worker errors are
sanitized before DB, audit, webhook and RQ persistence. Operators still
need cgroup CPU/memory/file limits, non-root isolated runtime and malware
inspection before releasing to actual users.

## Opt-in controls

- `PDFHUB_GRAYSCALE_PDF_TOOLS_ENABLED=false` on API/Worker in Compose.
  Disabled route omitted from OpenAPI and queue/worker reject execution.
- `NEXT_PUBLIC_PDFHUB_M30_GRAYSCALE_ENABLED=false` at Web build.
  Disabled card absent from the staged catalog; browser is not authorization.
- `pdf:grayscale` is available for explicit Admin/Service-Key grants, but
  excluded from new service-key default scope sets.
- No change to the original legacy 13-tool card inventory, M18 image
  extraction, M08/M09 password handling or other PDF operations.

## Acceptance evidence

Tests include real two-page red/green/blue PDF sources, render pre/post
conversion with Poppler and verify actual equal R/G/B output pixels, text,
page count and geometry, independent real Worker and owner-scoped stored PDF,
source hash, missing/wrong-owner/expired/MIME/scope/invalid body, encrypted,
corrupt, symlink, form, disabled feature, engine failure and storage
compensation. No regression CI or mocked fixture is an independent RCAT
production quality claim.

Do not mark M30 `VERIFIED` or `RELEASED` until actual Google Workspace
`@rcat.ac.th` identity, real Thai document goldens, production-like
Ghostscript isolation, antivirus, memory/time load, retention and human
release approval have been performed. No deployment or flag activation
is authorized by this PR.
