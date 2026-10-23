# T90-0.10 — Worker Heartbeat and Supervised Lease Recovery

**Tracker:** [#172](https://github.com/yiwssx/rcat-pdf-hub/issues/172) · **Base:** [Draft PR #182](https://github.com/yiwssx/rcat-pdf-hub/pull/182).

## Objective and scope

The opt-in, token-fenced T90 Worker from revision 0006 now periodically renews its lease, and an operator can diagnose and *quarantine* a demonstrably abandoned job. This does **not** introduce automatic job resumption, lease stealing, file deletion, or background recovery scheduler.

### Lease heartbeat

- Enabled **only when** `PDFHUB_ARTIFACT_WRITE_JOURNAL_ENABLED=true`. This setting remains **false by default**.
- `PDFHUB_ARTIFACT_HEARTBEAT_INTERVAL_SECONDS=30` (validated 5–300 s) defines a bounded heartbeat interval. The existing lease is max configured RQ processing timeout + 900 seconds.
- Runs in a daemon thread with **its own SQLAlchemy Session**, so blocking OCR, LibreOffice, PDF conversion or self-hosted S3 I/O does not block heartbeats.
- Each heartbeat performs a database compare-and-swap on `job_id`, `status=running`, `lease_token`, and **non-expired** `lease_expires_at`; only then updates expiry. Cancelled, completed, wrong-token and expired attempts cannot be revived.
- Database failures are retried at the next tick; definitive CAS rejection sets `lost`. The worker checks the lost signal before storage reservations and before final publication. The existing SQL-fenced completion gate remains the final authority.
- Heartbeat stops when the Worker exits (success, cancellation, caught failure). This prevents periodic DB writes after a job completes.

### Read-only stale lease inventory

```sh
python -m app.supervised_recovery --limit 50
```

This queries only the configured DB, does **not** query Redis, mutate jobs, or delete files. Reports expired, still-running fenced attempts including exact token/epoch and number of unresolved `planned` / `needs_review` journal entries. Protect the report: tokens must not be exposed via tenant API, frontend, public logs or user-download metadata.

### Explicitly supervised quarantine

Only after inspecting the job and RQ state, an authorized operator may invoke:

```sh
python -m app.supervised_recovery \
  --quarantine-job-id '<job-id>' \
  --expected-token '<exact-token-from-inventory>' \
  --expected-epoch '<exact-epoch-from-inventory>' \
  --acknowledge quarantine-without-requeue-or-delete
```

Fail-closed gates enforced in the application:

1. Exact expected epoch and token, `status=running`, and **expired** lease.
2. RQ reference must be present. The CLI obtains a fresh RQ status directly from Redis; only `failed`, `stopped`, `canceled`, or `finished` is accepted. Active/queued RQ, Redis timeout, unknown/missing RQ or an unverifiable status rejects the operation.
3. Published `output_file_id` or linked `JobOutputArtifact` blocks quarantine.
4. Required audit event must succeed before state mutation.
5. Database CAS reconfirms status, lease token, epoch, expiry and lack of primary output; on success revokes token, increments epoch, marks job failed for **manual review**.
6. Journal rows and storage objects are preserved. The action **does not** requeue, retry, resume, publish, restore or delete any file. New attempts require a separate, explicitly authorized job and its own UUID.

### Failures explicitly not resolved here

- This step does not guarantee an external PDF process stops immediately if its lease is invalidated; the database fencing still blocks publishing, and per-attempt names prevent overwriting another worker. Quarantine must only run against demonstrably terminal RQ states.
- PostgreSQL transaction-level races, Redis/RQ liveness windows, multi-node process failure, S3 cleanup and real Worker SIGKILL remain **staging/load tests**, not proven Production behavior.
- No production S3 connection, PostgreSQL backup-clone rehearsal, production migration, deployment or feature activation.
- Automated takeover, automatic purge, scheduler-driven mass quarantine and heartbeat lease-stealing are prohibited until independent review.
- `0006` migration and subsequent downgrade still require operator approval: downgrading below 0006 destroys journal evidence.

### Acceptance checklist

- [ ] Heartbeat CAS renews a live token; cannot revive expired/cancelled or another worker's token
- [ ] Background heartbeat executes during blocking work and terminates after work
- [ ] Two simultaneous claimers: one success only; second cannot publish
- [ ] Stale inventory dry-run, terminal RQ verification and audit fail-closed quarantine tested
- [ ] Existing local/S3 fake fault-injection tests and isolated PostgreSQL 18 migrations pass
- [ ] Core API CI green; feature flag **OFF**, Draft PR only, no merge/deploy
