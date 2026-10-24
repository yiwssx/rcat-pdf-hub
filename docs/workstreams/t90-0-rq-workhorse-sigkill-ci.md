# T90-0.13 — Actual RQ work-horse SIGKILL and supervised recovery CI gate

**Master tracker:** [#172](https://github.com/yiwssx/rcat-pdf-hub/issues/172) · **Stacked on:** [Draft PR #186](https://github.com/yiwssx/rcat-pdf-hub/pull/186)

## Why

T90-0.11 killed a **direct Python process** executing `process_job`, not an RQ-forked work-horse. That established the journal and orphan persistence, but did not establish what real RQ/Valkey considers terminal after the forked work-horse disappears. T90-0.13 adds that acceptance scenario without altering production behavior.

## New real-stack CI scenario (fourth in existing gated test harness)

- Only runs in explicitly gated GitHub Actions on an isolated PostgreSQL 18 database, loopback Valkey/RQ, and disposable SeaweedFS bucket. Reuses #184's isolated harness.
- Enqueues a **real RQ job** and starts a real RQ parent Worker. The Worker forks a work-horse child. The child uses deterministic tiny PDF output but invokes the real storage SDK and writes to SeaweedFS. After the actual PUT and while the worker is in-progress, the child writes a temporary marker with its **own PID and parent PID** then atomically renames it.
- Test controller verifies the PID is NOT the RQ parent, parent PID matches the RQ supervisor, RQ status is `started`, stored S3 object exists, and DB job/journal are `running` / `planned` without a FileRecord. Then sends **SIGKILL only to the forked work-horse PID** (not its supervisor).
- The genuine RQ parent handles its work-horse death and exits. Controller queries **fresh RQ status**, which must be in the exact operator recovery terminal allowlist (`failed`, `stopped`, `canceled`). Unknown, stale, queued, started and finished are **not** accepted as proof.
- Even with terminal RQ evidence, manual recovery **must reject** the Job before lease expiry. The harness sets the expiry into the past **in its disposable test DB only**, emulating expiry plus the five-minute grace. An inspected dry-run and the actual audited operator recovery then mark the old Job failed and revoke the token with exact epoch/fencing (no new Job).
- Assertions confirm `artifact_write_journal` remains `planned`, no FileRecord/JobOutputArtifact was published, orphaned S3 bytes remain physically stored, and a recovery-request audit event was written. **No automatic object deletion, takeover or requeue** occurs.
- Prior three real-stack probes (two RQ processes/duplicate delivery, direct child SIGKILL, and real PUT + injected ACK loss) remain mandatory.

## Isolation and limits

- All RQ/Redis/S3/PostgreSQL resources exist only in a disposable CI context. Only SIGKILL test child belongs to the CI process tree; never send signals based on user-controlled identifiers.
- CI uses synthetic data and a stub PDF compression routine **only**; RQ forking/parent reaping, DB transactions, object storage and OS SIGKILL are real.
- It does not test losing the **RQ parent supervisor**, Redis failover, multi-node stress, lost audit storage, S3 network partitions or production-like data.
- No new production modules or DB migration. No scheduled recovery or automatic purge, no merges, no deployment, no feature flags activated. Existing journal and multi-output flags remain OFF.

## Acceptance

- [ ] Real forked RQ work-horse killed after S3 PUT and supervisor records terminal status.
- [ ] Manual recovery blocked before lease expiry; succeeds only with verified RQ status and matching epoch after grace.
- [ ] Journal, S3 object and audit evidence preserved; no FileRecord or job-output published.
- [ ] All four real-stack scenarios and complete CI validation PASS.
- [ ] Draft PR and tracker updated; stop after this task.
