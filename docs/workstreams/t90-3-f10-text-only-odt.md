# T90-3 F10 — PDF to editable ODT (strict text-only subset)

This converter produces a **genuine, editable OpenDocument Text package**
(\`.odt\`), not a renamed ZIP or one bitmap screenshot per page.

The supported subset is deliberately narrow: only source PDF pages with
unambiguous selectable text from one left-aligned column. It reuses the
reviewed F14 text extraction constraints and **rejects** raster/scanned
documents, images and embedded XObjects, drawings, grids/tables, multicolumn
layout, rotated/transformed text and unsupported page geometry. It does not
promise preservation of page sizes, font metrics, decorative styles or
complex Thai typography.

- Strict input: max 16 MiB, 12 pages, 150,000 Unicode characters.
- Actual OASIS ODF content: uncompressed first ZIP member \`mimetype\`,
  valid \`content.xml\` editable \`text:p\` nodes, \`styles.xml\` and correct
  \`META-INF/manifest.xml\`. Page boundaries use \`fo:break-before=page\`
  paragraph style. XML escaped by ElementTree.
- Output: \`.odt\`, \`application/vnd.oasis.opendocument.text\`, max 4 MiB;
  exclusive file creation and complete package CRC/inventory validation.
- API: \`POST /api/v1/pdf/from-pdf/odt\`, owner-bound \`file_id\`, existing
  scope \`pdf:pdf-to-image\`, full original PDF signature/owner/expiry/MIME
  checks also repeated inside the worker, heavy queue, feature flag
  \`PDFHUB_FROM_PDF_TOOLS_ENABLED=false\` by default.
- Tests: real selectable generated PDFs, exact editable paragraphs and
  page-break markers, manifest/MIME and ZIP structure, encrypted/symlink/
  overwrite guards, ownership, and (where available) genuine LibreOffice
  reopening into a 2-page searchable PDF.

**No claim of production acceptance:** RCAT Thai source-vs-output fidelity,
actual institutional OIDC account ownership, target host sandbox and malware
scanning, operator live pilot and rollback evidence remain separately gated
in T90-5. Do not activate this experimental converter based on source CI.
