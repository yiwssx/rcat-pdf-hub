# T90-0.6 — Database migration readiness gate

**Status:** Reviewable implementation and regression suite; **NOT approved for Production**.  
**Owner tracker:** [#172](https://github.com/yiwssx/rcat-pdf-hub/issues/172)  
**Parent draft:** [#178](https://github.com/yiwssx/rcat-pdf-hub/pull/178) (job artifact listing + UI)

## Inspection and finding

The additive migration `0005_t90_output_artifacts` creates `job_output_artifacts` and backfills completed job outputs from `jobs.output_file_id` **only where** the source FileRecord exists and its `source_system` equals the Job `requested_by`. It does not rewrite the historical job/file rows or primary download pointer.

The original compound unique constraint `UNIQUE(job_id, role, ordinal)` **does not** prevent a second primary row because `ordinal=NULL` is allowed on `result` and `bundle`, and SQL databases generally permit multiple nulls under an ordinary UNIQUE constraint. Having two roots violates the manifest guarantee and forces the result listing to fail closed.

## Fix in this PR

- Keep existing compound unique key and role/ordinal CheckConstraint.
- Add dialect-portable **partial unique index** `uq_job_output_artifacts_one_primary` on `job_id` **WHERE role IN ('result', 'bundle')** in both the SQLAlchemy model and Alembic `0005`.
- Include index drop in `0005` downgrade. This preserves multiple numbered `part` artifacts but forbids multiple `result`/`bundle` roots for one job.
- Migration `0005` is **not yet merged into main or deployed**, so correction belongs in its original revision rather than a new follow-on migration.

## Isolation and reproducibility

`apps/api/tests/test_t90_migration_lifecycle.py` starts a **fresh SQLite file** or an **adopted legacy SQLite file without an Alembic version**, seeds historical completed, queued, failed, wrong-owner, missing-output and null-output jobs, then:

1. Upgrades to `0005` through the actual Alembic `run_migrations()` path.
2. Checks only eligible same-owner completed results are linked; verifies ZIP=`bundle`, normal PDF=`result`, and historical job/file records are unchanged.
3. Verifies primary partial-unique index and FK/index metadata, and rejects a second root, duplicate part number, invalid ordinal and nonexistent job FK.
4. Downgrades safely to `0004` without modifying historical Job/File records.
5. Re-upgrades and reconfirms deterministic, owner-safe backfill.
6. A third test upgrades a fully fresh SQLite database and verifies the partial unique index's exact predicate.

The test invokes isolated Python processes to avoid polluting cached application DB settings or the test fixture's database. It runs automatically in the existing pinned API image under `scripts/backend-coverage.py` / full backend validation.

## Release decision

**Do not enable `PDFHUB_MULTI_OUTPUT_ARTIFACTS_ENABLED` yet.** Before merging/deploying, rehearse `0004→0005→0004→0005` on a disposable PostgreSQL clone from an actual sanitized backup; measure lock duration, index creation and backfill on realistic row volume. Verify snapshot/restore and all owner scope and S3 object-orphan recovery gates separately. SQLite tests show correctness of migration logic, **not** Production PostgreSQL approval.

The current PR adds no API, Web, feature enablement, production settings or database operation on live infrastructure.
