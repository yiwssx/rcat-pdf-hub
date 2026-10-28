# T90-1.4 — Document Info, searchable text, and limited XMP removal (staged)

Parent [#225](https://github.com/yiwssx/rcat-pdf-hub/issues/225) · Master [#172](https://github.com/yiwssx/rcat-pdf-hub/issues/172).

## Scope and accepted engine boundaries

This Draft adds a **separate reviewed internal module**
`apps/api/app/services/pdf_document_data.py`, but intentionally does **not**
enable tool IDs M13/M17/M27. T90-0's 13-operation allowlist, Phase-0
source/parameter guards, disabled tool routes, queue distribution,
authorization, retention, storage and production config remain untouched.

- **M13, Edit metadata (staged):** update or selectively delete *document
  information dictionary* /Title, /Author, /Subject, /Keywords.
  Thai Unicode round trip, at most four allowed fields and 512 characters per
  field, reject control characters and unknown keys. Fail closed if any root
  or page XMP is present: silent XMP/Info disagreement is unacceptable.
- **M17, Extract text (staged):** UTF-8 plain text from existing searchable
  text layers with form-feed page delimiters, including Thai font fixtures.
  Bound to 1–1000 pages, 16 MiB decoded page content and 8 MiB total text.
  Fail explicitly on an image-only document (OCR required). No claims about
  semantic reading order, tables, hidden text, or OCR accuracy. Materializing
  decoded streams can itself be resource-intensive; a separate hard OS-level
  memory/time budget is required before activating this on the public worker.
- **M27, Remove metadata (staged):** rebuild the document, clear document Info,
  root /Metadata and page-level /Metadata (XMP), collect and drop orphan
  objects, then read the output again and verify supported dictionaries are
  empty/missing. Test raw sentinel bytes are not left in a representative
  output. **This is NOT redaction/sanitization of all private data.**
  Annotations, /PieceInfo, forms, embedded files, attachments, XMP inside
  other objects, signatures, JavaScript, revision history hidden in content,
  pixel data and identifying page content are NOT certified erased.
- Both PDF-writing operations use an adjacent temporary file, strict output
  parsing and atomic rename; all three reject equal input/output paths,
  encrypted/corrupt inputs and preserve source bytes.
- No dependency change. Pinned pypdf version from API lock is 6.21.2.

## CI acceptance

- [ ] Real PDF metadata round trip and Thai text tests execute in pinned API image.
- [ ] Info/XMP removal proves absence from normal dictionaries AND loss of raw
  orphaned sentinel strings (not a universal secrets scan).
- [ ] Missing text, invalid fields, malformed/encrypted PDFs and same path fail closed.
- [ ] Core API CI, Web CI, CodeQL both languages, Dependency Review pass.
- [ ] No changed 13 adapter registry, auth scopes, queue, public routes or feature flags.

## NOT implemented by this Draft

API endpoint models, operation scopes, Web UI, queued job persistence, artifact
MIME/output specs for text/plain, owner-scoped downloadable TXT, real Compose
run and download, signed URL/expiry policy for TXT, document-level XMP editing,
OCR fallback, content/redaction guarantees and public feature rollout. These
require a separately reviewed route/worker/release-controlled contract change,
full integration QA in T90-1.8 and Production signoff in T90-5.

**Registry M13/M17/M27 stay PLANNED, runtime disabled; 0/90 RELEASED.**
Do not mark them VERIFIED or merge/activate from a unit-test-only CI pass.
