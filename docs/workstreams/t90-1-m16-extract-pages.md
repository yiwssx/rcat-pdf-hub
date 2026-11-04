# T90-1 / M16 — Extract pages (source-code delivery)

**Tracker:** #225 (T90-1), #172 (master), #262 (institutional acceptance).

## Scope
M16 is a **dedicated** owner-bound Extract Pages workflow, not a renamed old
`split` call. The existing legacy `POST /api/v1/pdf/split` and M07
`POST /api/v1/pdf/split-to-zip` remain unchanged.

- `POST /api/v1/pdf/extract-pages` takes `{file_id,pages,format:"pdf"|"zip"}`.
- `pdf` creates one genuine PDF containing selected source pages in the
  specified order (pypdf; not raster/renaming).
- `zip` creates a deterministic ordered ZIP of genuine individually usable
  one-page PDFs using the already reviewed M07 ZIP engine, plus a separate
  owner-bound FileRecord/Artifact for each page.
- Supports the bounded range grammar `1,3,5`, `5-3`, `1-z`, `z-1`,
  preserving explicit order and rejecting duplicates, missing and out-of-range
  page references.
- Source PDF is immutable. Strict PDF signature, source owner, expiry, persisted
  MIME/filename, parameters and feature flags checked at API and **again** by
  Worker. `pdf:split` permission required for submission and job management.
- Maximum source **16 MiB / 200 pages**, maximum selected **80 pages**, maximum
  exported PDF content **64 MiB** and ZIP bundle **64 MiB**.
- Signed, encrypted, annotated and interactive form source PDFs are outside this
  reviewed subset and rejected. Full Thai visual/layout equivalence is NOT
  certified.
- The preexisting artifact pipeline provides malware scan, aggregate quota,
  attempt fencing, audit and transactional Storage + DB commit, cancellation,
  safe compensation on partial uploads, and authenticated per-file downloads.
- Frontend split/organizer screen offers page-selection and range-based M16
  actions; result page labels ZIP parts as genuine PDFs.

## Feature gates (ALL default OFF)
- Backend: `PDFHUB_EXTRACT_PAGES_TOOLS_ENABLED=false`.
- ZIP additionally requires `PDFHUB_MULTI_OUTPUT_ARTIFACTS_ENABLED=true`.
- Browser build: `NEXT_PUBLIC_PDFHUB_M16_EXTRACT_ENABLED=false` unless
  explicitly enabled. Browser exposure never bypasses backend authorization.
- No migrations, server deployment, environment toggling or Production release.

## Validation
- Actual PDF binary content/page order/geometry/source immutability, including
  descending ranges, for combined PDF and ZIP.
- Strict request schema, tenant ownership, expiry, MIME, page limits,
  encrypted/symlink/overwrite, auth scope and disabled-queue refusals.
- DB-backed Worker tests verify one PDF result vs ZIP bundle + two independent
  PDF part records, owner and storage consistency, cancellation/flag revocation
  and compensation after a simulated partial part-storage failure.
- Merge gate: exact PR-head Core API CI, Web CI, CodeQL, Dependency Review
  must all succeed. **Do not** claim `VERIFIED`, `RELEASED`,
  production-ready Thai documents or independent acceptance until RCAT pilot.
