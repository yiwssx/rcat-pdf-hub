# T90-0.11 — Real Redis/RQ, PostgreSQL and self-hosted S3 chaos gate

**Parent:** [T90 Master Tracker #172](https://github.com/yiwssx/rcat-pdf-hub/issues/172) · **Previous PR:** [#183](https://github.com/yiwssx/rcat-pdf-hub/pull/183) · **Scope:** one CI-only integration gate

## Purpose

The previous T90 tasks verified Worker fencing and Storage/S3 compensation primarily through SQLAlchemy unit tests, a disposable PostgreSQL 18 migration suite, and simulated S3 adapters. This task exercises the *actual system boundaries*:

- Two independent Python **RQ Worker processes** sharing a live, ephemeral **Valkey 8.1.9** queue, with concurrent deliveries of the same DB Job ID.
- A live disposable **PostgreSQL 18.6** database, migrated using the application's standard Alembic path.
- Real SDK HTTP traffic (PUT/GET/HEAD/DELETE) to a disposable, self-hosted **SeaweedFS 4.44** S3-compatible server.
- Real OS `SIGKILL` of a separate process executing `app.worker_tasks.process_job`, after a successful S3 upload but **before FileRecord commit**.
- A separate lost network-acknowledgment fault: actual upload to SeaweedFS succeeds and the subprocess deliberately raises a synthetic connection error; the actual application compensates using real S3 HEAD/DELETE.

The PDF compression routine is replaced only *inside the dedicated test child* by deterministic local PDF bytes. This isolates queueing, database, storage, fencing and crash behavior from PDF engine performance and input complexity. Existing ordinary PDF regression tests remain in the regular CI step.

## Isolation gates

1. A dedicated GitHub Actions step starts fresh Valkey and SeaweedFS containers using the **same pinned image versions** as the Compose stack, both bound to runner loopback. These containers exist only for the CI job and are removed by a shell trap.
2. The controller refuses to run unless **`GITHUB_ACTIONS=true`**, **`PDFHUB_T90_STACK_ENABLED=yes`**, and a *specific* PostgreSQL administrator / loopback SeaweedFS endpoint are present. No user-supplied remote target is accepted.
3. It creates a random dedicated PostgreSQL database (`pdfhub_t90_stack_*`), a random SeaweedFS bucket (`pdfhub-t90-ci-*`), and uses **Redis database 15** on the *ephemeral CI-only* Valkey service. Random queue names avoid collisions.
4. It turns on the journal flag **only in this temporary test process**. No application/production flag, Docker Compose or environment file is changed.
5. The controller terminates leftover test child processes, deletes temporary S3 objects/bucket, flushes only CI Redis database 15, and drops only its uniquely allocated PostgreSQL database. No file deletion in any Production namespace is possible from this test configuration.

## Integration acceptance scenarios

| Test | Expected result |
|---|---|
| Two genuine RQ worker processes, duplicate deliveries of the same Job ID | Exactly one committed primary output, exactly one committed journal entry, single fencing epoch and valid S3 object |
| `SIGKILL` at the injected point after successful SeaweedFS upload and before SQL commit | Job remains running, durable `planned` entry survives, object is physically present but has **no FileRecord**; a nonterminal queued RQ reference cannot authorize recovery |
| Real SeaweedFS PUT succeeds, synthetic lost network acknowledgment raised | Worker exception path compensates with real S3 deletion; Job is failed, journal is `compensated`, no output FileRecord or leaked object |

The forced SIGKILL scenario executes the *real application worker task in an isolated subprocess*, but it is **not** a kill of an RQ-managed work-horse process. RQ end-of-life handling after a killed work-horse remains a separate real Redis/RQ supervisor lifecycle test. The held RQ reference is intentionally **queued**, ensuring the manual-recovery gate rejects it rather than treating a disappeared process as terminal. No actual network cable/device is disconnected; the lost ACK is fault-injected *after* a real SeaweedFS PUT. Do not describe this as a complete network-partition test.

## Release blocks still open

- No multi-host/multi-node RQ load test, worker-pool capacity benchmark, or prolonged outage/reconnect soak test.
- No actual kill of an RQ-managed work-horse and subsequent RQ terminal-status recovery confirmation.
- No repeated S3 multipart or transient network partition during upload, MinIO/Ceph compatibility pass, or object-store retention integration.
- No production-equivalent sanitized DB backup and restore rehearsal; no long-running migration performance/lock investigation.
- No merge, Production deploy, flag activation or automatic orphan deletion/requeue.

**Feature flags remain OFF in the repository and Production.** Success of this CI gate is necessary but **not sufficient** for enabling multi-output storage or the journaled Worker.
