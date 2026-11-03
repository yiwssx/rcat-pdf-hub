# T90-3 F05 — Genuine EPUB 3 from selectable PDF text (engineering stage)

The converter emits **reflowable EPUB3 XHTML**, not screenshots or a PDF
renamed to \`.epub\`. Each accepted PDF page becomes one XHTML chapter with
editable text. TOC and EPUB spine preserve original page order.

- **Input:** one verified, unexpired, owner-bound PDF; strict parse, no
  encryption, <=16 MiB, <=12 pages, <=150,000 Unicode characters.
- **Supported source subset:** a single left-aligned, selectable text column
  on each page. Refuse scanned pages, images, drawings, tables, multi-column
  and transformed/rotated text or malformed geometry. No invented chapter
  hierarchy or visual layout reconstruction.
- **Output:** true \`application/epub+zip\` package with first *stored*
  \`mimetype\` member, \`META-INF/container.xml\`, OCF EPUB package, EPUB3
  navigation \`nav.xhtml\`, ordered XHTML content pages and manifest/spine.
  Includes no external assets or URLs; metadata uses an opaque random UUID
  rather than the source-document hash; language is 'und' (undetermined).
- **Bounds:** <=4 MiB EPUB, checked ZIP inventory/CRC; exclusive creation,
  source immutable. Generated XML uses safe element-escaped text.
- **Routing:** \`POST /api/v1/pdf/from-pdf/epub\`, strict \`file_id\`, owner
  and permission scope \`pdf:pdf-to-image\`; source ownership, MIME, expiration
  and signature rechecked at API and worker; heavy queue; default-disabled
  \`PDFHUB_FROM_PDF_TOOLS_ENABLED\`.
- **Automated checks:** real 1/2-page PDF fixtures, EPUB XML metadata and
  nav/spine, exact text in output XHTML, encrypted/symlink/overwrite,
  scanned/graphics and source/owner/MIME/expiry failures.

**Excluded:** Thai font/linebreak page fidelity, embedded images, structured
tables, genuine headings and links, original PDF appearance and DRM. These
require separate source-specific engineering and physical RCAT QA. This PR
does **not** assert T90-5 VERIFIED or RELEASED and must not activate flags.
