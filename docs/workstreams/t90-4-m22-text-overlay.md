# T90-4 M22 — bounded source-code stage: Add text to PDF

Issues: https://github.com/yiwssx/rcat-pdf-hub/issues/261 and https://github.com/yiwssx/rcat-pdf-hub/issues/262.

## Implemented source code

- Authenticated, owner-bound POST /api/v1/pdf/advanced/add-text; requires pdf:stamp scope.
- API validates source owner, expiry, PDF MIME/name, bounded input and strict parameters.
- Worker independently validates owner, expiry, signature and exact persisted parameter keys.
- Real ReportLab vector text merged into exactly one original PDF page using pypdf.
- Input is not modified; unaffected page content is checked after output creation.
- Printable ASCII only, 1–120 characters, Helvetica 8–24 pt, pages 1–80.
- Source file <= 16 MiB, output <= 32 MiB; text placement in PDF bottom-left point coordinates.
- Rejects encrypted, annotated, rotated and interactive-form PDFs, symlinks, output overwrite, malformed or out-of-bounds coordinates.
- PDFHUB_PDF_TEXT_OVERLAY_TOOLS_ENABLED is OFF by default, so router is not mounted.

## Explicitly NOT certified

- No Thai shaping/font embedding, Unicode other than ASCII, image editing, redaction, signatures, general annotations or drag/drop UI.
- Real RCAT Workspace OAuth owner download, Thai goldens, visually inspected page fidelity, AV/isolation, accessibility, quotas and operator rollout are deferred.
- CODE-ONLY engineering stage; NOT VERIFIED and NOT RELEASED; no production activation.

## Acceptance

- Run pinned API-image regression tests test_t90_4_m22_text_overlay.py and test_t90_4_m22_staged_api.py.
- Exact-head Core API, Web CI, CodeQL and Dependency Review must pass before merge.
- Independent T90-5 source credit must cite merged source SHA and CI; it is not automatic.
