# T90-3 F14 — Text-only PDF to editable RTF (engineering slice)

RTF is **genuinely editable plain text**, not raster screenshots.
Source PDF paragraphs are extracted through pypdf and encoded as RTF Unicode
escapes (UTF-16 code units, signed for RTF), with one \`\\par\` per source
line and \`\\page\` between PDF pages. This does not preserve arbitrary
PDF typography, graphics, tables, spatial layout or font metrics.

- Only pages with selectable unambiguous text from a single left-aligned
  column; rejects scanned/image PDFs, XObjects, vector drawing commands,
  transformed text, multicolumn/indented/wrapped ambiguity, rotated pages,
  control bytes and encrypted source.
- Max 16 MiB PDF, 12 pages, 150,000 source characters, 3 MiB RTF output.
- Fixed \`application/rtf\` MIME; output created exclusively, source immutable.
- \`POST /api/v1/pdf/from-pdf/rtf\` with owner-bound \`file_id\`, existing
  authorization \`pdf:pdf-to-image\`; source MIME/signature/expiry and ownership
  rechecked in worker; heavy queue; default-OFF
  \`PDFHUB_FROM_PDF_TOOLS_ENABLED\` guard.
- Tests use real PDF pages with actual selectable paragraphs, correct
  output RTF headers/page breaks, Unicode escaping, negative graphic and
  multicolumn cases, encrypted/source replacement and API ownership checks.

**Not independently accepted:** authentic Thai fonts/ligatures and reader
rendering, real RCAT institutional PDFs, target-host AV and security
isolation, Google Workspace login/download and operator signoff. No
T90-5 VERIFIED or RELEASED status from this code.
