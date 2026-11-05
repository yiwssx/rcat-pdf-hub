# T90-1 / M31 — Header & Footer PDF

Tracks: #225 (T90-1), #172 (master), #262 (independent acceptance).

## Feature delivered in source

A dedicated `POST /api/v1/pdf/header-and-footer` accepts one user-owned PDF
and a bounded six-field overlay configuration. It queues the independent
`header-and-footer` operation and requires `pdf:header-footer` authorization.
A staged Web form provides separate header/footer text, alignments
(left/center/right), font sizes and margins. Accepted placeholders are
`{page}` and `{total}` (with escaped braces possible); any other format
fields, Python conversion or format specifications are rejected.

The actual PDF engine is an extension of the existing tested M31 staged
ReportLab/pypdf overlay implementation. This integration corrects explicit
Unicode font selection, uses embedded Noto Sans Thai where installed and
rejects unsupported Unicode substitution rather than silently showing
missing glyphs. Existing rotated input is normalized to display orientation
before overlay; mixed paper sizes remain supported. The source PDF is not
modified and the validated result is published to a new file atomically.

## Guardrails

- Up to **16 MiB PDF input**, **200 pages**, **32 MiB output** and PDF
  dimensions 72–2880 points. Zero-origin, uncropped page boxes only.
- Header and footer text each max **256 characters**; no control or bidi
  formatting chars; at least one nonempty value. Format strict template
  syntax with `{page}` and `{total}` only.
- Font size **8–24 pt**, margin **12–144 pt**, alignments only left/center/right.
  All settings must be explicitly typed in Worker; unknown persisted
  parameters are rejected. Text widths must fit the selected page.
- Input source must be a genuine unencrypted PDF and owned by the
  authenticated principal; API and Worker independently check ownership,
  PDF MIME/extension, expiry, length and Worker verifies signature.
- Signed, annotated, form-containing, cropped, non-origin and unsupported
  page geometry documents fail closed. Even on accepted PDFs, the header
  or footer **overlays** (does not reflow) original content. It may obscure
  existing content in the margin; no redaction, signature preservation,
  PDF/A continuity, or precise Thai glyph shaping is guaranteed.
- On failure, generic M31 errors are persisted and reported without raw
  untrusted PDF/parser paths. Normal AV, storage journal/fencing, quotas,
  retention, authenticated download and rollback remain inherited.
  Header/footer outputs are not automatically sent to Paperless.

## Default-OFF operation

- API/Worker: `PDFHUB_HEADER_FOOTER_TOOLS_ENABLED=false` (default);
  route omitted from OpenAPI, queue and Worker fail closed if disabled.
- Web build: `NEXT_PUBLIC_PDFHUB_M31_HEADER_FOOTER_ENABLED=false`
  (default). Staged tool is separate from the immutable legacy 13-card
  registry. Browser flags are not server authorization.
- The independent `pdf:header-footer` scope can be explicitly granted by
  Admin, and is excluded from newly created service-key default scopes.
- No credentials, host changes, Production deployment or feature activation
  included in the PR.

## Acceptance contract

Automated tests cover actual two-page mixed portrait/landscape PDFs with
one rotated page, correct extracted original/header/footer ASCII text,
placeholder totals, dimensions and normalized orientation, and bounded
Thai overlay with embedded fonts. Negative tests cover unknown/malicious
placeholders, Unicode control marks, too-long text, small margins,
oversized fonts, encrypted/signed/form/annotated inputs, symlinks, existing
destinations, cross-owner/scope/expiry/MIME, flags, tampered Worker
parameters, storage failure compensation and no Paperless auto-archive.

Required exact-PR-head GitHub CI: Core API, Web CI, CodeQL, Dependency
Review; merge only after all green and no unresolved review threads.

**Engineering CI does not constitute independently VERIFIED or RELEASED.**
Before enabling the RCAT institutional service, separately validate real
Thai educational documents, font shaping/rendered margins, signed document
policies, PDF/A constraints, Google Workspace `@rcat.ac.th` identity,
multi-user security, memory/load/resource isolation and operator approval.
