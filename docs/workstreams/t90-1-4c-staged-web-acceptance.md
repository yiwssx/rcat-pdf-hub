# T90-1.4c — isolated staging Web intake (engineering subunit)

Tracks [#225](https://github.com/yiwssx/rcat-pdf-hub/issues/225) and depends on unmerged draft [#231](https://github.com/yiwssx/rcat-pdf-hub/pull/231) (which includes #230).

## Delivered in this subunit
- Private, server-gated `/staged/document-data` page with **two** explicit opt-ins: `PDFHUB_STAGED_DOCUMENT_WEB_ENABLED=true` and `PDFHUB_DOCUMENT_DATA_TOOLS_ENABLED=true`. Both are absent/false by default. The server renders HTTP 404 without both. Dynamic rendering avoids static-build exposure.
- Owner-scoped client selection from the authenticated file library, checking persisted `application/pdf`, size > 0 and expiry. The API and worker each recheck authorization and input.
- Three explicit forms and API calls:
  - M13 `POST /api/v1/pdf/document-data/edit-metadata`, supported Info fields only (title/author/subject/keywords), selected empty fields become `null` removal.
  - M27 `POST /api/v1/pdf/document-data/remove-metadata`, only Info and root/page XMP; **not anonymization or full redaction**.
  - M17 `POST /api/v1/pdf/document-data/extract-text`, existing searchable text to UTF-8 TXT; scanned-only PDFs require OCR.
- Explicit job result link after HTTP 202, and scope, MIME, empty-file, expired-file and owner-side preflight messages. Backend remains the security authority. No catalog, public slug, API rule, 90-tool release state or production flag is modified.

## Follow-on integration test added for this review
- `apps/api/tests/t90_stack_probe.py` now has a fifth, independent **real Thai PDF** scenario. Under `GITHUB_ACTIONS=true` on disposable PostgreSQL 18, Valkey/RQ and SeaweedFS S3, it temporarily enables only the staged backend flag, creates an owner-owned searchable Thai PDF in storage, authenticates through the **real opt-in API**, and enqueues an actual RQ worker process.
- It inspects the persisted TXT `text/plain; charset=utf-8` S3 object, original input immutability, JobOutputArtifact relation, owner-only download, signed URL and rejection of a different owner.
- This is a **CI-only ephemeral stack rehearsal**, not the full deployed Compose Browser journey, production quota/AV proof or manual Thai visual acceptance. A new test is **not a PASS until the exact commit's Core API CI is green**.
- Additional Playwright scenarios verify fail-closed missing scopes and omitted metadata field selection; result label is tied to actual submitted operation.

## Evidence gates
- [ ] Web CI main production-build typecheck and standard Playwright suite, including default-OFF 404.
- [ ] Independent opt-in Playwright scenario in Web CI with both flags scoped to that single test step; owner/MIME filtering, metadata Thai/null, distinct operations, result link.
- [ ] Core API CI; CodeQL Python/JS; Dependency Review on exact PR head.
- [ ] Authenticated *real* Docker Compose RQ/Valkey + S3/NAS/SeaweedFS download with AV/quotas and Thai golden corpus (separate reviewed staging rehearsal).
- [ ] Security review of pre-existing wildcard file-reader semantics before asserting comprehensive tenant isolation. No Production acceptance until fixed/reviewed.
- [ ] Accessibility keyboard/screen reader and mobile viewport validation against a live staging deployment, plus resource/expiry/cancellation/failure load tests.

## Exclusions
No merge, deploy, real database migration, production secret change, flag activation or claim of full metadata sanitization. Existing 13 operations unchanged and the planning registry still disabled. **0/90 RELEASED**. T90-1.4 and 1.4c remain open until integration gates above are satisfied.
