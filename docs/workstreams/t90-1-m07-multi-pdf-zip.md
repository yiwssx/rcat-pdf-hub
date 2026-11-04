# T90-1 M07 — bounded per-page PDF ZIP engineering

Related: #225 #262 #172.

## Delivered in source code
- Retains legacy single-PDF POST /api/v1/pdf/split semantics.
- New POST /api/v1/pdf/split-to-zip with strict owner/MIME/expiry/size/range validation, pdf:split scope and independent worker signature/owner recheck.
- Requires BOTH PDFHUB_SPLIT_ZIP_TOOLS_ENABLED=true AND PDFHUB_MULTI_OUTPUT_ARTIFACTS_ENABLED=true; both default OFF. Route invisible in default OpenAPI.
- Produces genuinely independent one-page PDFs in ordered ZIP members, no raster conversion; no repeated pages.
- Caps original at 16 MiB and 200 pages; at most 80 selected pages, 64 MiB ZIP and 64 MiB total individual PDF files.
- Reuses job quotas, AV, rollback/compensation, write-journal fencing, and transactionally persisted owner-bound FileRecords + one ZIP bundle and individual parts.
- Existing /api/v1/jobs/{job_id}/artifacts and authenticated /api/v1/files/{file_id}/download expose owner-scoped individual PDFs.
- UI button requires NEXT_PUBLIC_PDFHUB_M07_ZIP_ENABLED=true at Web build; default OFF. Results screen uses per-PDF labels.

## Explicit non-goals / acceptance deferred
- Source forms, signatures, and annotations rejected. No claims of Thai visual fidelity, signed-document preservation, accessibility, production host acceptance or full 90-tool completion.
- Source code is NOT independent VERIFIED/RELEASED evidence. Production flags must remain OFF.
- Do not deploy or run live RCAT tests without separate operator approval.

## Tests
- Real PDF binary per-page order/text/geometry/source immutability plus descending page syntax, archive integrity, malicious ZIP members, invalid pages, encrypted/symlink/overwrite, strict request/owner/flag tests, and DB-backed worker atomicity/rollback.
- Exact-head Core API CI, Web CI, CodeQL, Dependency Review required before merge.
