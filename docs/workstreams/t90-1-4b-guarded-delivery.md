# T90-1.4b — Guarded API, scoped queue execution and typed output MIME

Stacked on [T90-1.4a engine PR #230](https://github.com/yiwssx/rcat-pdf-hub/pull/230), parent [#225](https://github.com/yiwssx/rcat-pdf-hub/issues/225), master [#172](https://github.com/yiwssx/rcat-pdf-hub/issues/172).

## Implementation boundary

**Staging-only:** `PDFHUB_DOCUMENT_DATA_TOOLS_ENABLED=false` is the default and is enforced by the existing fail-closed T90-0 architectural validator. The new API router is **not included in the main app** and therefore does not appear in OpenAPI unless the flag was explicitly enabled before app creation. Each handler rechecks the flag.

- `/api/v1/pdf/document-data/edit-metadata`: PDF Info field selection and validated Thai strings, `pdf:metadata` scope.
- `/api/v1/pdf/document-data/remove-metadata`: limited document-Info/root/page-XMP clearing, `pdf:metadata` scope. **Not redaction.**
- `/api/v1/pdf/document-data/extract-text`: searchable text layers to UTF-8 TXT, `pdf:extract-text` scope. Scanned input still requires OCR.
- All three reject foreign-owned FileRecords, expired files, and persisted non-PDF MIME **before enqueue**; input ownership/MIME/expiry is rechecked at worker execution.
- Legacy `ADAPTERS` remains exact 13; new allowlist is a distinct, static, flag-guarded `STAGED_ADAPTERS` mapping. RQ scheduling uses existing interactive/PDF queues with unchanged legacy operation allowlists.
- For `extract-text`, worker output type is `text/plain; charset=utf-8` and suffix `.txt` instead of a misleading `.pdf`; existing FileRecord/JobOutputArtifact, owner/expiry/quota/audit/AV/write-journal paths persist the correct type and allow authenticated/signed download through the existing file router.
- Retry explicitly requires the new operation scope; newly disabled staged operations cannot be retried.
- Tests cover default hidden routes and OpenAPI, true FastAPI session/SQLAlchemy authorization and job enqueue, real adapter PDF/TXT output, UTF-8 Thai and immutable sources, queue routing, invalid parameters and kill-switch.

## Acceptance gates

- [ ] exact-head Core API CI + full backend/Python 3.11–3.14, isolated PG18, Valkey/RQ/SeaweedFS and pinned image pass
- [ ] Web CI + mocked visual gallery, CodeQL Python/JS and dependency review pass
- [ ] Disabled-by-default proof and no drift in the 13 legacy static route/adapters/scopes
- [ ] Real staging flag-ON worker → storage → owner-scoped signed TXT download with cancellation/expiry is **not yet fully integration tested** (T90-1.4c).

## Deployment decisions

The flag must **not** be turned on by this PR, no production migrations, production deployment, or changes to the 90 registry. M13/M17/M27 remain `PLANNED` and runtime disabled in the canonical tool registry (0/90 RELEASED). Further QA and release controls are mandatory before merging/activating new tools.
