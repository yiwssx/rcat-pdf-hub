# M01 — Scoped text-object PDF editing (Engineering First)

**Source capability:** one exact, same-length printable ASCII text replacement inside a visible Tj string, within one bounded TJ positioning array, or across exactly two adjacent Tj text-showing operators, using built-in Courier/Helvetica/Times or narrowly validated embedded TrueType fonts on a specified page. This edits the **existing content stream**, rather than drawing text over it. It produces a separate PDF and retains the input unmodified.

## Explicitly supported

- Plain, unsigned, unencrypted, unannotated, unrotated, uncropped PDF with 1–80 pages and an input size up to 12 MiB.
- Built-in Courier, Helvetica or Times Type1 text remains supported with standard/WinAnsi encodings and AFM width compensation. New: single-byte embedded TrueType only if the original file contains FontFile2, explicit /Widths and a bounded 1-byte identity /ToUnicode map; *every replacement ASCII glyph must already occur visibly on the same page in the exact same font resource*. Nonmatching/subset glyphs are rejected, never guessed.
- Page index 1–80, exact source text 3–96 printable ASCII characters occurring exactly once in either one Tj operator, a single TJ array with up to 64 operands / 32 text strings, or two directly adjacent Tj operators in the same BT/ET text object with no intervening operation. For TJ cross-fragment replacements, only bounded glyph kerning gaps (≤120 text-space units) are accepted. Each changed fragment must retain its own space count, and the overall replacement must retain character and space counts.
- Courier retains a single original Tj operation; Helvetica/Times insert AFM-calculated width compensation. Two consecutive Tj operators are combined into one equivalent TJ array, retaining their exact string-fragment boundaries and allowing only literal single-byte ASCII source bytes. Embedded fonts use their explicit /Widths for the reused ASCII character codes. TJ edits preserve source kerning operands and place one combined displacement AFTER the edited glyph span, keeping word fragments contiguous and subsequent text aligned. No covering overlay or transparent fake edit.
- Per-account file ownership and expiry checks at API and Worker, signed-in session and existing pdf:stamp scope, bounded output, on-disk PDF verification and unchanged source checksum.
- Queue routing only when the backend PDFHUB_PDF_EDIT_TEXT_TOOLS_ENABLED flag is true.

## Not supported — do not claim full PDF Editor

Arbitrary PDF text, Thai/Unicode, unknown font cmap, missing glyphs in embedded subsets, custom/broken font widths, 2-byte composite CID fonts, embedded Type1/CFF, TJ arrays with large spacing gaps, text spanning three or more Tj operators, across an intervening command, between a Tj and TJ, or with changing fonts, repeated matches, XObject text, scanned pages, annotations/forms/signatures, complex layout editing, secure redaction and in-place source edits. These remain fail-closed.

Even with a valid source, readers may interpret embedded PDF operator state differently. Keep real-host/Thai/visual fidelity and release acceptance under the deferred QA track.

## Independent activation safety

- API + Worker: PDFHUB_PDF_EDIT_TEXT_TOOLS_ENABLED=false (default), independent of existing M22 text-overlay flag.
- Staged Web route /staged/edit-text requires both PDFHUB_STAGED_PDF_EDIT_WEB_ENABLED=true and PDFHUB_PDF_EDIT_TEXT_TOOLS_ENABLED=true (both default OFF). A source merge never enables either.
- Production R1 preflight fails when experimental backend flag is enabled. No Compose, DNS, secrets, RBAC, network or Production changes.
- Developer regression covers adjacent Tj text operators, ambiguous duplicate matches, intervening text-state refusal, real multi-fragment TJ content with preserved source spacing, built-in font AFM compensation, real embedded TrueType PDF samples without shipping any font binary, missing-glyph and missing-ToUnicode refusal, immutable source, page integrity and existing default-OFF owner/scope safeguards.

**Inventory classification:** PARTIAL (M01). A verified narrow literal text replacement is real engineering work, but is not a full general-purpose PDF editor.
