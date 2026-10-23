# T90-0.8 — Storage write compensation and crash-orphan detection

**Tracker:** [#172](https://github.com/yiwssx/rcat-pdf-hub/issues/172) · **Predecessor:** [#180](https://github.com/yiwssx/rcat-pdf-hub/pull/180) · **Mode:** opt-in development, no live release.

## Observed failure modes

1. `store_staged_file(...)` may upload to self-hosted S3 and then raise (lost acknowledgment or completion error). The earlier worker appended the stored name **after** the call, so it had no reference to remove a partially uploaded object.
2. If the worker is killed after S3/local storage succeeds but **before** database commit, Python exception handlers never execute. The storage object remains without a `FileRecord`. Existing `/admin/storage-reconciliation` reports such objects but does not distinguish old failed T90 jobs from active jobs or unrelated user files.
3. A re-run that collides with a saved output filename must not overwrite an already committed `FileRecord` or delete that file when compensating.

## Implemented in this PR

- `storage.planned_processed_stored_name(filename)` computes the exact local or S3 destination before writing (preserving the existing file naming and download compatibility).
- Worker registers the **planned** primary/part key in its compensation list *before* calling storage. If the upload later throws, the worker attempts deletion even without a returned storage key. It refuses destinations that already belong to a saved FileRecord and rechecks FileRecord ownership of the object before deletion on rollback.
- Extend `storage_reconciliation` read-only local and S3 inventory with last-modified evidence. Current Admin reconciliation response schema and categories remain unchanged.
- New `python -m app.artifact_recovery` read-only operator diagnostic. Searches **only** generated names under managed `processed/`: `<uuid>.pdf`, `<uuid>.zip`, `<uuid>-page-0001.png/jpg`. Requires terminal **failed/cancelled** JobRecord, no referencing FileRecord anywhere, a valid timezone-aware object timestamp, and **at least 24 hours** age. Pending/running, completed, unknown, recent, unmanaged originals or ambiguous files never become candidates. Does not auto-delete or sign links.
- Tests simulate S3 writing bytes then raising before returning, cleanup success and cleanup network failure, local/S3 orphan scans, retained files, protected active/completed jobs, unknown names and age/timezone guards.

## Operator-only dry run

Use **only after checking the configured storage and database are the intended environment**:

```sh
python -m app.artifact_recovery --min-age-hours 24 --detail-limit 50
```

Report fields: `dry_run=true`, `auto_delete=false`, `eligible_count`, bounded candidate metadata. This command never issues `DELETE` to local storage or S3. Do not schedule this against a live database without authorization; it is a diagnostic only.

## Deliberate exclusions / release blockers

- **No automatic orphan deletion**: job state alone plus age cannot prove the worker is no longer uploading; deletion needs lease/fencing token or a durable journal and a lock/concurrency policy.
- No durable write-ahead object journal or guaranteed recovery from `SIGKILL`, power loss or process crash. The report identifies likely leftovers for manual review, not conclusive proof of safe deletion.
- No production S3 integration test, multi-worker concurrency test, real S3 crash/restore or sanitized PostgreSQL backup rehearsal. Unit tests use a fake self-hosted S3 client.
- No deployment, migration, feature toggle change, new UI operation, changed file-download authorization or expansion of the 90 tool execution surface.
- Existing 24-hour minimum grace and filtered listing prevent accidental immediate deletion, but **candidates must still be reviewed**. Do not interpret this as production-ready automated garbage collection.

## Acceptance

- [ ] Tests for simulated partial S3 upload, failure cleanup and read-only orphan candidate filtering pass
- [ ] Host Python, pinned backend validation, migrations and regression checks pass
- [ ] No merges, no Production changes and no enablement of `PDFHUB_MULTI_OUTPUT_ARTIFACTS_ENABLED`
