# M18 — Extract embedded images from PDF

Engineering scope: #225, #172. Acceptance: #262.

## Behavior and limits

The dedicated owner-scoped `POST /api/v1/pdf/extract-images` extracts real
embedded PDF image objects (through pypdf), **not page screenshots**, into
a deterministic ZIP. It accepts only decoded PNG/JPEG images; unsupported
image encodings and PDF documents without embedded images fail clearly.
For a visible image of every page, users must use the separate PDF-to-images
rasterization tool.

M18 restricts input to verified unencrypted PDFs, at most **16 MiB** and
**200 pages**. The export allows at most **80 image objects**, **64 MiB**
total decoded image bytes, **64 MiB ZIP** and **30 million pixels** per
image. The worker repeats source owner, expiry, persisted MIME, original
file signature and exact empty parameter validation. No cross-owner wildcard
exception exists at the API layer.

Output is one ZIP containing safe server-generated names such as
`page-0002-image-0001.png`. When the separately gated preexisting
`PDFHUB_MULTI_OUTPUT_ARTIFACTS_ENABLED` is true, each ZIP image is validated,
scanned and persisted as an individually downloadable tenant-owned FileRecord.
The existing storage-journal, quota, malware check, cancellation, rollback
and authenticated download paths are reused; otherwise the ZIP remains
a complete usable single downloadable artifact.

## Rollout boundaries

- `PDFHUB_EXTRACT_EMBEDDED_IMAGES_TOOLS_ENABLED=false` by default. The new
  API route is not registered and the Worker/Queue reject M18 unless enabled.
- `NEXT_PUBLIC_PDFHUB_M18_EXTRACT_ENABLED=false` at Web build time hides
  the staged card. Browser gating is not authorization.
- `pdf:extract-images` is its own grantable permission; it is excluded
  from new service-key default grants.
- The legacy 13-tool UI/operation contracts and existing page-rasterization
  behavior remain unchanged. No production deploy or flag activation.

## Acceptance criteria and known limitations

Automated tests use real embedded graphics, validate original source hash,
binary extracted pixel dimensions, ZIP member safety, wrong-owner/scope/expiry
denial, corrupted and encrypted PDFs, absent images, invalid image bytes, and
storage failure/compensation with owner-scoped independent images.

PDF images may be recompressed by pypdf when decoded, and page rendering
is not equivalent to extracting original XObjects. Embedded JPEG2000, TIFF
and other special formats are not yet supported. There is no independent
claim of colorspace/ICC/CMYK/transparency exact fidelity, full Thai corpus,
production host resource limits or real Google Workspace access.

Mandatory CI on exact PR head: Core API CI, Web CI, CodeQL and Dependency
Review. Code merge is not acceptance. Leave M18 independently NOT VERIFIED
and NOT RELEASED until the physical RCAT/Thai/OIDC/AV/security gates pass.
