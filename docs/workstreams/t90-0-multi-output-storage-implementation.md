# T90-0.4 — Multi-output persistence, first opt-in vertical slice

**Status:** DRAFT / DEVELOPMENT — do not deploy or enable in Production.  
**Tracking:** [#172](https://github.com/yiwssx/rcat-pdf-hub/issues/172)  
**Dependency:** T90-0.3 proposed output manifest (#176)

## Scope and what is implemented

This slice adds **real database associations and independently stored image files** for the existing `pdf-to-images` operation, but leaves the current single ZIP download and the 13 existing PDF operation interfaces intact.

- `JobOutputArtifact` association model + Alembic `0005_t90_output_artifacts` migration: job/file foreign keys, role (`result`, `bundle`, `part`), ordinal, constraints, indexes and same-owner backfill for already-completed historical jobs.
- All newly completed 13 existing operations create a `result` or `bundle` association, maintaining `JobRecord.output_file_id` as the legacy primary pointer.
- When `PDFHUB_MULTI_OUTPUT_ARTIFACTS_ENABLED=true` **only**, PDF-to-images continues to create the ZIP, then extracts, independently malware scans and stores each page image under the owning `FileRecord` and association. Parent ZIP remains `role=bundle`; children become ordered `part` rows.
- Aggregate quota gate includes **bundle plus all pages**. The extraction imposes a 200-page ceiling, safe generated basenames, contiguous page sequence, valid PNG/JPEG bytes and an additional bounded decompressed byte budget. The ZIP itself retains the existing configured page-count gate.
- The final FileRecords, job-artifact links, existing `output_file_id` and completed job status are committed in **one DB transaction**, and a concurrently canceled job cannot be marked completed by an unconditional late update. In-process store failures roll back DB and delete already stored objects best-effort.
- File deletion, expired retention cleanup and terminal job-history deletion clear corresponding association rows; DB foreign keys provide additional integrity on PostgreSQL.

## Default and rollout discipline

`PDFHUB_MULTI_OUTPUT_ARTIFACTS_ENABLED` defaults to **false**, so an ordinary deployment continues the old ZIP-only result behavior (the association table is additive after migration). This PR **does not** set it true, change Compose/prod overrides, update UI, add document-processing operations, or ship job artifact listing endpoints.

Before enabling in Production, independently review:
- Source/worker Docker builds and migration on actual PostgreSQL with existing data and adopted Alembic history.
- Full integration of local/NAS and self-hosted S3: cleanup of orphaned objects after worker crashes, retries, S3 upload failure injection, aggregate storage quotas and repeated activation.
- Dedicated authenticated listing of individual job outputs: **not included**; the existing owner-scoped File Library may still display these new child FileRecords if feature flag is on. Any new endpoint must preserve job and file ownership/expiry and not expose signed URLs automatically.
- Storage growth: ZIP and individually persisted pages **count separately**, by design. Load-test max-image artifacts, memory, disk, retention and malware handling, including multi-user concurrency.
- Rollback: keep flag off and revert application code if needed. The additive migration can remain, and `jobs.output_file_id` + ZIP results remain readable.

## Limitations and remaining work

- This is one operation-specific first slice, **not** a universal multi-output engine, not 90 functional PDF tools, and not the runtime implementation of `pdf-output-manifest.v1.schema.json`.
- No new Web UI download cards, job-artifacts GET route, separate per-page PDF splitting, or per-item signed-share URLs.
- The existing file access rules remain unchanged; permissions and human wildcard scope hardening require separate security review.
- Filesystem/S3 object storage is not transaction-aware. DB operations are transactional; deletion of uncommitted storage is **best effort**, and future crash-recovery reconciliation is required before production enablement.

## Required verification

- [ ] `apps/api/tests/test_multi_output_storage.py`: default flag ZIP-only, opt-in ZIP+two child images, quota atomicity, failure cleanup, malicious ZIP names/contents and decompression limits
- [ ] Migration both fresh and adopted databases in Core API CI; retained backfill test
- [ ] Existing `scripts/validate-tool-artifacts.py` and previous T90 contract gates green
- [ ] Full Core API CI suite green, code/permissions/security review
- [ ] No production deploy/merge until reviewed, and stop after this one task
