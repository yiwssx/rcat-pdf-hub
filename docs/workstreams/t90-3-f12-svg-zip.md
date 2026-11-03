# T90-3 F12 — PDF to SVG (engineering stage)

One already-verified owner-bound, unexpired PDF produces **one ZIP** with a
separately serialized SVG image for each PDF page (`page-0001.svg`, etc.).
An SVG is an image, **not a promise of editable text**: Poppler may convert
glyphs to vector paths and embed images. No fabricated editable document.

- `POST /api/v1/pdf/from-pdf/svg`, `file_id` only; scope `pdf:pdf-to-image`.
- Existing heavy queue, authenticated owner-scoped artifact download, audit,
  scanning, retention and quota; ZIP `application/zip` (not an SVG MIME).
- Default-disabled `PDFHUB_FROM_PDF_TOOLS_ENABLED` check at API and worker.
- Strict source PDF signature/owner/MIME/expiry validation in both layers,
  no encrypted PDFs, max 24 MiB, 12 pages, no symlinks or existing outputs.
- Sandboxed non-shell Poppler `pdftocairo -svg` **per page** with a 50-second
  per-page timeout and child CPU/AS/NOFILE/FSIZE limits. A page must render
  and pass strict defusedxml inspection before entering the ZIP.
- Reject XML entities/DTDs, scripts, external SVG hrefs, stylesheet `url()`
  references beyond local fragments, and active SVG elements. `href` references
  to local fragments or inline PNG/JPEG data are accepted; no network fetching.
- Limit 12 MiB per SVG and 72 MiB for the complete ZIP, and verify sorted page
  names, every page, page count, stored ZIP members and CRC. Fail closed on any
  missing/malformed page, without returning a partial ZIP.
- Tests cover actual 2/10-page Poppler SVG, different page graphics, immutable
  input, malicious XML, existing output, encrypted PDF, owner, expiry, source
  MIME, disabled flag and queue/output MIME.

**Not certified:** target RCAT host sandbox/AV/runtime checks, real Thai
text/layout and vector fidelity comparisons, authenticated Google Workspace
institutional SSO and independent operator release signoff. Do not activate
or promote T90-5 beyond IMPLEMENTED based on code tests.
