# M01 — Scoped text-object PDF editing (Engineering First)

**Source capability:** one exact, same-length printable ASCII text replacement inside one visible Tj string using a standard built-in Courier font on a specified page. This edits the **existing content stream**, rather than drawing text over it. It produces a separate PDF and retains the input unmodified.

## Explicitly supported

- Plain, unsigned, unencrypted, unannotated, unrotated, uncropped PDF with 1–80 pages and an input size up to 12 MiB.
- Existing single string in Courier, Courier-Bold, Courier-Oblique, or Courier-BoldOblique Type 1 font, Standard or WinAnsi encoding, with no ToUnicode or embedded font descriptor.
- Page index 1–80, exact source text 3–96 printable ASCII characters occurring once in one Tj operator, and distinct replacement of the same character count. Fixed width keeps word advance stable.
- Per-account file ownership and expiry checks at API and Worker, signed-in session and existing pdf:stamp scope, bounded output, on-disk PDF verification and unchanged source checksum.
- Queue routing only when the backend PDFHUB_PDF_EDIT_TEXT_TOOLS_ENABLED flag is true.

## Not supported — do not claim full PDF Editor

Arbitrary PDF text, Unicode/Thai, subset or proportional fonts, TJ positioned glyph arrays, multiple occurrences, multi-run text, text in XObjects, scanned image editing, annotations/forms/signatures, arbitrary layout editing, secure redaction, faithful round-tripping of unknown document classes, or modification of the source in place.

Even with a valid source, readers may interpret embedded PDF operator state differently. Keep real-host/Thai/visual fidelity and release acceptance under the deferred QA track.

## Independent activation safety

- API + Worker: PDFHUB_PDF_EDIT_TEXT_TOOLS_ENABLED=false (default), independent of existing M22 text-overlay flag.
- Staged Web route /staged/edit-text requires both PDFHUB_STAGED_PDF_EDIT_WEB_ENABLED=true and PDFHUB_PDF_EDIT_TEXT_TOOLS_ENABLED=true (both default OFF). A source merge never enables either.
- Production R1 preflight fails when experimental backend flag is enabled. No Compose, DNS, secrets, RBAC, network or Production changes.
- Developer regression covers actual PDF stream edit, page integrity, duplicate, wrong font, encrypted PDF, invalid text, output and default-OFF/owner/scope UI.

**Inventory classification:** PARTIAL (M01). A verified narrow literal text replacement is real engineering work, but is not a full general-purpose PDF editor.
