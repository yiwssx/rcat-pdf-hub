# T90-0.10 — Worker Heartbeat and Controlled Expired-Job Recovery

**Workstream:** T90 foundation · **Master Tracker:** [#172](https://github.com/yiwssx/rcat-pdf-hub/issues/172) · **Predecessor:** [PR #182](https://github.com/yiwssx/rcat-pdf-hub/pull/182)

## Objective and safety boundary

The durable journal and claim-once fencing in T90-0.9 already reject duplicate RQ deliveries. A long PDF-to-images/OCR/Office conversion, however, previously had a **single lease deadline**. A long-running or blocked task could outlive that fixed deadline. An abruptly terminated RQ worker could also leave a `running` JobRecord and `planned` journal entries indefinitely.

This stage provides **bounded lease renewal while a worker process is alive**, and a **human-invoked, independently verified transition to Failed** for expired jobs whose matching RQ task is *already terminal*. It does not implement automatic takeover/retry/deletion.

## Implementation

- `app.write_journal.renew_execution_lease(...)` uses one atomic SQL `UPDATE` with `job_id`, `status=running`, **exact token and epoch**, and **unexpired existing deadline**. Once expired, cancelled, failed or superseded, the deadline can **never** be resurrected by a late heartbeat.
- `app.worker_heartbeat.WorkerHeartbeat` runs a daemon thread with a **separate short-lived database Session**, 20-second default periodic renewal and 180-second default TTL. There are no shared SQLAlchemy Sessions across threads. Renewal stops on changed/terminal token, and cleanup stops/joins the thread with a bounded wait.
- Heartbeats run **only** with existing `PDFHUB_ARTIFACT_WRITE_JOURNAL_ENABLED=true` (still **false** by default); the previous ZIP/PDF/worker workflow is unchanged while the flag is false. All writes, progress changes, output publishing and completion remain guarded by SQL predicates, so a lost/failed heartbeat cannot authorize a stale write.
- Configurable `PDFHUB_LEASE_HEARTBEAT_INTERVAL_SECONDS` (5–300; interval must be strictly below ⅓ of TTL), `PDFHUB_LEASE_HEARTBEAT_TTL_SECONDS` (61–3600), and `PDFHUB_LEASE_RECOVERY_GRACE_SECONDS` (60–86400). Invalid unsafe intervals fail closed during setup.
- `app.lease_recovery` reads the existing JobRecord and **live Redis/RQ job**; validates matching RQ identifier, worker function and argument, required epoch, status `running`, empty primary output, **lease expiry + grace**, and **no committed journal entry** for that execution.
- Recoverable RQ statuses are strictly `failed`, `stopped`, and `canceled`. Unknown, missing, queued, started, deferred, scheduled or finished statuses **never** authorize mutation. If RQ is unavailable, recovery fails closed.
- Dry-run is the default. Only an explicitly requested `--apply` with a named operator and matching epoch writes a `job.lease_recovery_requested` audit event first, then uses **compare-and-swap** on the same job, token, epoch, RQ id, status and deadline to mark it `failed`, revoke token, retain all journal entries, and write `job.lease_recovered` audit. There is **no** object deletion, queue enqueue, automatic attempt takeover, or change to the existing Retry API.

## Operator runbook — manual only, never a scheduled daemon

Execute from a trusted API container or shell with the correct environment after confirming the target job and matching RQ job ID. Record the observed `lease_epoch`; it is an anti-stale confirmation.

```bash
python -m app.lease_recovery --job-id <JOB_UUID> --expected-epoch <INTEGER> --operator <OPERATOR_ID>
# After reviewing the dry-run evidence and checking RQ really stopped:
python -m app.lease_recovery --job-id <JOB_UUID> --expected-epoch <INTEGER> --operator <OPERATOR_ID> --apply
```

Apply does not retry. If the input files are still valid and the user explicitly requests a retry, existing `POST /api/v1/jobs/{job_id}/retry` creates a **new job** with its own attempt, quota and permission checks. Never manually mark the old job queued or delete its journal until retained objects have been inspected.

**Safety prerequisites:** backing migration `0006_t90_write_journal` installed; flag explicitly reviewed and enabled; a working Redis/RQ connection; known operator identity; operator has independently checked that no worker is using the old RQ job. A queue entry that has simply disappeared from Redis is **not** proof that the worker is dead.

## Verification and non-goals

- Concurrent Worker sessions racing to claim one queued job: only one wins.
- Heartbeat extends only a live, correct, matching token+epoch; wrong token/epoch, expired or terminal states fail closed.
- Simulated heartbeat loop stops after token revocation; invalid heartbeat cadence refused.
- Manual recovery dry-run does not mutate. Live/finished/missing/wrong-RQ/too-early/stale-epoch/committed-journal/audit-failure attempts refuse mutation.
- Manual recovery after terminal RQ state retains planned objects, revokes the old fence, records audit events, and makes retry possible **only via the existing authorized job API**.
- PostgreSQL 18 CI adds real multi-session concurrent claim/renew/revoke/terminal recovery test alongside migration lifecycle, in disposable CI databases.

**Explicit limitations:** No active-RQ cancellation, no forced takeover of live workers, no automatic requeue, no background recovery scheduler, no auto-purging Journal or S3 objects, no guaranteed avoidance of a stale process writing its **unique attempt-scoped object** after expiry (the SQL final commit remains fenced), no real self-hosted S3 + RQ multi-process chaos/stress test, and no production deployment. Tests demonstrating overlapping Sessions are **not** substitutes for full multi-worker load tests.

**Rollout:** PR remains Draft, feature flags OFF by default. Production approval requires sanitized PostgreSQL clone/recovery checks, real Redis/RQ and S3 testing, lock/concurrency analysis and supervised release.
