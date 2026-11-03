# T90-3 F03/F04 — PDF to complete JPG/PNG page ZIPs (engineering)

Two specific end-user routes reuse a **single guarded Poppler raster engine**
but each produces the selected, true image format for **every PDF page**.
No first-page-only fallback, silent dropped pages or misleading single
multi-page JPEG/PNG. Output is an authenticated \`application/zip\`
containing exactly \`page-0001.jpg\`... or \`page-0001.png\`..., in order.

- \`POST /api/v1/pdf/from-pdf/jpg\` = F03, JPEG/ZIP.
- \`POST /api/v1/pdf/from-pdf/png\` = F04, PNG/ZIP.
- \`file_id\` with strict DPI 72–200 (default 96), existing scope
  \`pdf:pdf-to-image\`, owner/expiry/MIME/extension guards at API and worker.
  Worker revalidates original PDF signature, exact \`dpi\` parameter,
  feature flag and actor ownership.
- Default OFF \`PDFHUB_FROM_PDF_TOOLS_ENABLED\`, heavy queue, legacy
  owner-scoped single bundle download and existing quota, audit, malware,
  retention and TTL pipeline.
- Input <=24 MiB, 20 PDF pages, strict PDF parsing, no encrypted sources,
  <=6M raster pixels per page and 40M aggregate, 72–200 DPI.
- Poppler \`pdftoppm\` without shell/network/remote asset loading; 75-second
  deadline, CPU/AS/FSIZE/NOFILE/core child limits, private temporary
  directory and fixed file names.
- Validate exact unique page indices including Poppler's zero padding,
  actual PNG/JPEG image formats and full image decode, bounded per-image
  <=16 MiB, aggregate <=96 MiB ZIP, ordered member inventory, ZIP CRC.
  Refuse unexpected artifacts, duplicates, missing pages and overwrites.
- Functional tests render generated 2/10-page PDF sources into both true
  image formats and check every page, image dimensions, page differences,
  source immutability and signed headers. Negative tests include invalid DPI,
  unsupported formats, encrypted PDF, symlink, existing output, owner,
  expiration, MIME and feature flag/queue mapping.

Images are **lossy/pixel raster** (JPEG) or noneditable PNG, not extracted
embedded image objects or reconstructed selectable PDF text. No implicit
OCR, ICC/alpha guarantees or all-PDF Thai font layout claim.

**Independent QA pending:** real original RCAT Thai/scan/vector documents,
visual/raster DPI review, target-host Poppler sandbox/AV/load/latency,
Google Workspace school-only OIDC upload/job/download and operator rollout.
Code CI must not promote these tools to T90-5 VERIFIED/RELEASED.
