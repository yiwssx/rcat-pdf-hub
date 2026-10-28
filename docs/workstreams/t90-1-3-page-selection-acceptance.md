# T90-1.3 — Page selection / safe deletion / single-file extraction

- Master: [#172](https://github.com/yiwssx/rcat-pdf-hub/issues/172)
- Core PDF tracker: [#225](https://github.com/yiwssx/rcat-pdf-hub/issues/225)
- Canonical IDs: **M07 Split (PARTIAL), M14 Delete pages (PARTIAL), M16 Extract pages (PARTIAL)**.

## Scope implemented in this Draft

**No new backend operation or public catalog route is enabled**. Reuse the existing reviewed `split` (qpdf) and `organize` (pypdf) static adapters, `pdf:split` authorization, owner-bound job creation and original-document retention.

1. A single shared bounded parser (`apps/api/app/page_ranges.py`) rejects malformed, zero, over-100000, or overlong qpdf ranges **before** split/rotate API jobs enqueue and before engine execution. Retain descending `5-3`, final-page `z` and comma semantics. This is syntax validation, not a guarantee that a PDF contains a requested page.
2. Existing page-organizer UI can explicitly select individual thumbnail pages for extraction to **one new PDF**, with order/rotations matched to the selected preview. Removing a page still submits only retained pages (the source is not overwritten), last-page deletion is blocked, and a reset button restores the original local selection.
3. Typed numeric-range UI preflight uses authenticated PDF page count, disallows malformed/out-of-range requests, and defaults to `1-z` instead of assuming every PDF has three pages.
4. Loading failures are shown rather than leaving an unhandled promise or stale thumbnails. The visual organizer fails closed for PDFs above its existing 1,000-page API selection cap; basic numeric range selection remains offered when page count is known.
5. Real `qpdf` binary tests inspect PDF page order/text/geometry and input immutability. Existing `organize` engine tests assert deletion and empty-selection denial; Playwright covers UI selection/reset/invalid-page behavior.

## Explicit non-goals and remaining acceptance

- **Per-page separate PDF files and ZIP bundles are NOT implemented by this PR.** A combined selected-page PDF is not falsely counted as independent multi-output extraction. M07/M14/M16 retain PARTIAL until those contracts and end-to-end functionality are separately verified.
- Existing default `PDFHUB_MULTI_OUTPUT_ARTIFACTS_ENABLED=false` and `PDFHUB_ARTIFACT_WRITE_JOURNAL_ENABLED=false` remain unchanged.
- T90-0 static no-activation/13-adapter policy remains intact; no new UI route, auth scope, job operation, database migration, dependency, queue topology or Production configuration.
- Await full Core API CI (qpdf must actually run), Web CI/Playwright, CodeQL and Dependency Review on the exact PR head.
- Real authenticated Compose → Worker → storage → owner-scoped download, Thai golden set, responsive layout, crash/failure soak, and production-approved rollout remain for T90-1.8/T90-5.
- Tool release accounting remains **0/90** and no production deployment is authorized here.
