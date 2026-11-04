# T90-3 F01/F11 — OCR and PDF/A as explicit guarded PDF output tools

These are **two real, separate T90 tool IDs** built on the existing
OCRmyPDF/Tesseract engines, not a renamed JPG/PDF or browser placeholder.

- F01: `POST /api/v1/pdf/from-pdf/ocr` returns a searchable PDF
  (`.pdf`, `application/pdf`). OCRmyPDF `--skip-text --output-type pdf` preserves
  selectable pages and adds OCR to scanned pages. Configurable vetted
  `eng`, `tha`, `tha+eng` or `eng+tha`, deskew/rotate options. No
  claim that every Thai glyph is recognized perfectly.
- F11: `POST /api/v1/pdf/from-pdf/pdfa` targets PDF/A-2 through
  `ocrmypdf --force-ocr --output-type pdfa-2` **only for scanned,
  image-only original PDF pages without annotations, AcroForms, text,
  or vector-painted marks**. Selectable-text pages are rejected:
  pinned Debian Ghostscript 10.0.0 contains a known `--skip-text` PDF/A
  corruption regression. This source limitation prevents the force mode
  from discarding existing selectable text. The output must retain the
  page inventory and carry uniquely identified PDF/A-2 XMP metadata.
  This is **not** an ISO 19005 conformance certificate; independent
  veraPDF validation remains mandatory before VERIFIED/RELEASED.
- Existing real engine `app.services.pdf_tools` and signed owner-scoped
  job/artifact pipeline are reused without bypassing quota, audit or AV.
- Both new routes are behind default-OFF
  `PDFHUB_FROM_PDF_TOOLS_ENABLED` and their own operation IDs
  `pdf-to-ocr` / `pdf-to-pdfa` on the heavy queue. They do not
  disable or change the existing public `/api/v1/pdf/ocr` and
  `/api/v1/pdf/pdfa` operation paths.
- API and worker independently check one owned, unexpired,
  original verified MIME/signature PDF and a restricted option schema.
  Strict parser: max 20 MiB input, max 12 PDF pages, finite bounded page
  geometry; output <=64 MiB; no encrypted PDFs, symlink sources or
  destination overwrites. Original and resulting PDF page inventory
  must match, and failure deletes the intermediate output.
- Automated tests cover real image-only and selectable PDF fixtures, page-count and
  source immutability, missing PDF/A XMP, malformed/unsafe flags,
  encrypted inputs, symlink/overwrite, default disabled, queue/MIME,
  source owner/expiry, and (where OCRmyPDF is available) real PDF/A-2
  command output and XMP metadata.

**Still pending RCAT physical acceptance:** original Thai documents and
mixed scanned/selectable text, Tesseract language availability on actual
host, independent veraPDF/ISO conformance and accessibility scans,
target-host sandbox/AV/resource limits, signed institution-only Google
Workspace OIDC upload/job/download, operator rollout and rollback.
Neither source CI nor a PDF/A identifier warrants VERIFIED or RELEASED.
