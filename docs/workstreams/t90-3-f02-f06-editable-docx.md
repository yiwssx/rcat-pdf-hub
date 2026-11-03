# T90-3 F02 / F06 — PDF to Word / DOCX (text-only subset)

Both tools return a **genuine editable DOCX**, not legacy binary \`.doc\`
and never a document of page screenshots. F02 is a generic Word export route
and F06 is the dedicated DOCX route; they intentionally share one honest
engine and produce the same modern Word \`.docx\` output.

- Inputs: only pages with unambiguous selectable single-column plain text.
  Rejects encrypted/scanned PDFs, images, vector drawing, grids/tables,
  rotated/transformed or multicolumn text, unsupported page geometry.
- Max source 16 MiB, 12 pages, 150,000 characters.
- Outputs a strict OOXML ZIP package with \`[Content_Types].xml\`,
  \`_rels/.rels\` and \`word/document.xml\`. Each line is an editable Word
  paragraph, and PDF page boundaries become genuine Word page-break
  elements. Text is safely XML-escaped.
- Output \`.docx\`, MIME
  \`application/vnd.openxmlformats-officedocument.wordprocessingml.document\`;
  max 4 MiB, ZIP page/part inventory and CRC check, exclusive destination.
- Default-OFF \`PDFHUB_FROM_PDF_TOOLS_ENABLED\`, strict \`file_id\`,
  \`POST /api/v1/pdf/from-pdf/word\` (F02) and
  \`POST /api/v1/pdf/from-pdf/docx\` (F06). Authorized owner, original
  PDF MIME/signature and expiry rechecked at API and worker; heavy queue.
- Tests verify exact editable Word XML text and page breaks, binary
  package integrity, owner/expiry, encrypted/symlink/overwrite negatives
  and optional real LibreOffice reopen to searchable two-page PDF.

**Limitations:** No complex typography/table/image faithful reconstruction,
no legacy \`.doc\` binary, no claims of native Thai font/line-layout QA yet.
Real RCAT institutional source files, Google Workspace OIDC owner download,
sandbox/AV, target-host performance and operator rollback remain separately
deferred under T90-5. Code merge is not VERIFIED/RELEASED.
