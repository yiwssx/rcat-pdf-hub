# T90-3 F07 — PDF ruled-table to real Excel XLSX (bounded subset)

One PDF page containing a full, explicitly drawn rectangular grid maps to
one genuinely editable Excel worksheet named \`Page N\`. F13's conservative
table parser is reused, ensuring no whitespace-inferred columns, no invented
headers/values, no OCR of scanned tables and no unsupported merged cells.

- PDF source must be unencrypted, owned and unexpired, max 16 MiB / 6 pages;
  each source page must have a complete axis-aligned grid with 2+ columns,
  header plus data rows, <=12 columns, <=60 rows and <=500 total cells.
- Reject source images/XObjects, malformed/incomplete grid, text outside the
  grid, multi-fragment cells, spreadsheet formula prefixes (=,+,-,@),
  rotated/transformed or scanned PDFs; values are **always strings**.
- Output genuinely editable OOXML \`.xlsx\`: valid content types, package
  relationships, workbook with ordered sheets and inline string cell XML.
  Each source row/column is preserved as one editable sheet cell; never
  rasterizes a PDF page into a spreadsheet image.
- MIME \`application/vnd.openxmlformats-officedocument.spreadsheetml.sheet\`,
  max 6 MiB ZIP, max 1 MiB XML per worksheet, package names/CRC validated,
  exclusive destination creation, source immutable.
- Default-disabled guarded route \`POST /api/v1/pdf/from-pdf/excel\`; heavy
  queue; API/worker both enforce owner, unexpired PDF MIME/extension/source
  signature and resource budgets. Existing owner-scoped retention, quota and
  malware pipeline.
- Tests: real drawn-grid PDFs to exact editable sheet cells (one/two pages),
  workbook package, optional LibreOffice re-open, invalid grid, formula,
  encrypted/symlink/overwrite, disabled flag and ownership.

Still pending independent T90-5 real RCAT Thai tables, merged cells, source
layout comparison, Google Workspace OIDC owner lifecycle, host isolation/AV,
load and release approval. Not a universal PDF table extractor and not
VERIFIED/RELEASED merely by source CI.
