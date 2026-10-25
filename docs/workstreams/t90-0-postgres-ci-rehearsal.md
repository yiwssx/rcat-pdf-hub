# T90-0.7 — PostgreSQL 18 migration rehearsal (ephemeral CI)

**Parent:** [#172](https://github.com/yiwssx/rcat-pdf-hub/issues/172) · **Follows:** [#179](https://github.com/yiwssx/rcat-pdf-hub/pull/179) · **Stage:** CI-only database acceptance, not Production release.

## What changed

The Core API CI job now starts **`postgres:18.6-bookworm`**, matching the pinned application PostgreSQL image in `docker-compose.yml`. The service has a fixed **test-only** role and password, exposed only to the temporary Actions runner. The existing pinned API test image executes `pytest -q tests/test_t90_postgres_migration_ci.py` against the loopback service.

The rehearsal guards against unintended databases: it only accepts a PostgreSQL+psycopg URL for `pdfhub_t90_ci` pointing to `postgres` on `127.0.0.1:5432` and requires `GITHUB_ACTIONS=true`. It creates a separate unpredictable `pdfhub_t90_ci_*` database for each scenario and drops it in `finally`. All migrations run through the existing Alembic entry points in isolated subprocesses. When the CI environment is absent, the tests skip during normal Backend Coverage runs; the explicit CI rehearsal must execute three non-skipped cases.

## Real PostgreSQL assertions

1. **Legacy migration path:** upgrade a clean PostgreSQL database to `0004`, seed completed ZIP/PDF jobs plus intentionally invalid foreign-owner, missing-file, queued, failed, and null-output jobs; upgrade through `run_migrations()` to `0005`.
2. **Pre-Alembic adoption:** create only historical SQLAlchemy core tables, seed the same data, then let `run_migrations()` stamp baseline and apply `0002–0005`. This reproduces the installer adoption path.
3. **Backfill correctness:** only same-owner completed outputs become linked; `pdf-to-images` becomes `bundle`, ordinary PDF becomes `result`. Original Job and File rows, ownership, primary `output_file_id`, and statuses must not change.
4. **PostgreSQL-specific constraints:** verify the filtered unique primary index in `pg_indexes`, reject second `result`/ `bundle` root, duplicate part ordinal, invalid 0/201 ordinals, and a foreign-key reference to a missing job.
5. **Rollback and replay:** downgrade `0005 → 0004`, verify the additive table is removed without affecting legacy Job/File records, then re-upgrade `0004 → 0005` and check deterministic, owner-safe links.
6. **Fresh install:** execute all migrations on a pristine PostgreSQL database and confirm `0005` is current with the filtered index.

This is a **disposable synthetic-data PostgreSQL rehearsal** using the actual production-pinned database version, **not a clone of the live RCAT database**. It does not inspect, import, anonymize, alter, or back up any Production data.

## Evidence and remaining release blockers

- [ ] PostgreSQL CI rehearsal completes all 3 cases; no fixture skipped in the dedicated step.
- [ ] Existing Backend + contracts and Gotenberg gates pass without regressions.
- [ ] Full production-equivalent sanitized-backup PostgreSQL rehearsal, migration duration/lock investigation, backup restore exercise and runbook sign-off (a **separate** step).
- [ ] Storage/S3 failure/restart reconciliation, retention, security and user acceptance (a **separate** step).
- [ ] Dependency PR stack review, merge sequencing, approval and release (not performed by this PR).

**Safety posture:** `PDFHUB_MULTI_OUTPUT_ARTIFACTS_ENABLED` stays **false** by default. The task adds CI tests and documentation only; it neither alters the T90 worker/UI code nor deploys an actual migration to RCAT infrastructure.
