# T90-3 F13 — PDF ruled table to CSV (code-only stage)

**Guarantee:** The engine does **not** claim to infer the original logical
columns of arbitrary PDFs. It accepts only pages consisting of a single,
fully ruled rectangular table and selectable, single-line text placed within
explicit cell boundaries. Anything ambiguous fails closed.

- Input one verified, owned, unexpired PDF; strict parser; 16 MiB, max 6 pages.
- Only axis-aligned, untransformed, *stroked* vertical and horizontal full-grid
  PDF paths; at least two columns, header plus data, <=12 columns, <=60 rows,
  <=500 total cells. Non-grid PDFs, diagonal rules, rotated/translated text,
  incomplete grids, multi-fragment cells, text outside table and embedded
  XObjects are rejected.
- All values remain **strings**. No inferred numeric types, merged cells,
  multline cells, OCR, scanned tables, nested tables, comments, free-form text,
  or undocumented page spans. Cells beginning with spreadsheet formula-like
  prefixes (=, +, -, @) are rejected, not silently rewritten.
- Output authenticated, owner-scoped ZIP \`application/zip\`, one BOM-marked
  UTF-8 CSV for **every PDF page**, in PDF page order (file names
  \`page-0001.csv\` etc.). No partial-success ZIP.
- Refuse source/output symlinks, output replacement, invalid pages or excessive
  resources; max 8 MiB entire ZIP. Worker rechecks persisted source owner,
  MIME, expiry and original PDF signature.
- API \`POST /api/v1/pdf/from-pdf/csv\` with exact \`file_id\`, existing
  \`pdf:pdf-to-image\` scope, heavy queue and **default-OFF**
  \`PDFHUB_FROM_PDF_TOOLS_ENABLED\`.
- Real ReportLab drawn-table fixtures prove correct CSV rows for one and three
  pages; negatives cover missing grid, non-table, spreadsheet formula,
  encrypted source, symlinks, owner, expiry, MIME and output preservation.

**Still deferred:** RCAT-owned files, Thai and font glyph/encoding fidelity,
real-world irregular table structures, live Google Workspace OIDC, target-host
security/isolation, AV, load, source-output manual comparison and operator
approval. T90-5 remains independent and no feature flags are activated.
