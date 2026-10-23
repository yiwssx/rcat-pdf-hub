# T90-0.9 — Durable artifact write journal and single-writer fencing

**Workstream:** 90-tool foundation · **Master tracker:** [#172](https://github.com/yiwssx/rcat-pdf-hub/issues/172) · **Stack dependency:** [#181](https://github.com/yiwssx/rcat-pdf-hub/pull/181).

## Problem

The previous implementation records successful output files atomically and compensates caught exceptions, but an ungraceful Worker termination can leave storage objects without `FileRecord` records. Duplicate RQ deliveries can also run the same job at once, sharing deterministic temporary and destination filenames. T90-0.8 offered read-only orphan detection but no durable per-write intentions or guarded job claim.

## Implemented (opt-in, OFF by default)

**New flag:** `PDFHUB_ARTIFACT_WRITE_JOURNAL_ENABLED=false`. Do not enable this independently of migration and review.

- Revision `0006_t90_write_journal` adds `jobs.lease_token`, `jobs.lease_epoch`, `jobs.lease_expires_at`, and durable `artifact_write_journal`. Existing rows gain epoch zero; no rewriting existing `jobs.output_file_id`. Journal entries are **not job-FK-cascaded** so administrative history deletion cannot silently destroy the only orphan write evidence.
- **Atomic claim-once** transition `queued → running` via database conditional UPDATE; duplicate/terminal/running jobs do not start a second output-producing worker. Execution token UUID and monotonically incremented epoch identify the attempt.
- All progress and final `running → completed` transitions are guarded by token and a deadline; a worker whose claim expires or is invalidated cannot publish FileRecords or mark a job complete.
- The deadline is at least the maximum configured RQ operation timeout **plus 15 minutes**. **No automatic takeover** after expiry; there is currently no heartbeat or proven recovery controller.
- Temporary PDF/ZIP and final `processed/` object names include a random attempt UUID to avoid old workers overwriting or deleting another attempt's files.
- **Pre-write transaction:** list all primary and page destinations, commit `planned` journal rows BEFORE the first object upload. FileRecords, job-artifact association, journal transition to `committed`, and successful JobRecord completion share the **final atomic database commit**. Failed storage operations use T90-0.8 best-effort per-key compensation, followed by persisted `compensated` or `needs_review` journal statuses.
- The legacy Worker path stays unchanged while the flag is off; no API/UI or PDF tool contract changes, no release.

## Accepted behavior and specific limitations

| Scenario | Fenced behavior |
|---|---|
| Duplicate RQ delivery | Rejected without another PDF output or journal row |
| Concurrent/stale token | Cannot update progress or commit outputs |
| Crash after journal commit | `planned` row remains in DB; no automatic deletion |
| Upload succeeds but response lost | Best-effort delete of isolated attempt destination; `compensated` or `needs_review` persisted |
| FileRecords + output commit | Journal transitions and Job completion in one DB transaction |
| Lease expires during a long PDF operation | Job may remain running; fail closed; require operator investigation |
| Worker `SIGKILL` | Journal survives, but full automatic restoration is **not implemented** |
| Existing Production | Flag off, no merge/deploy/migrations without signoff |

This stage **does not** provide heartbeats, fenced lease takeover, durable claim renewal, automatically deleting planned objects or requeueing an expired job. Those require a separate supervised recovery workflow that checks actual RQ liveness and storage ownership. A journal entry alone is not proof an object can be deleted. Journal history is intentionally retained until explicit operator-reviewed cleanup. Existing `artifact_recovery` inventory uses legacy generated filename patterns; new attempt-scoped entries can be examined through the journal table and must not be automatically cleaned up.

## Required rollout gates

- [ ] Isolated SQLite and PostgreSQL 18 migrations `0004→0005→0006`; re-upgrade/adoption and reverse to `0004` in test databases.
- [ ] Backend unit and simulated lost ACK/crash tests for the opt-in worker, plus CI coverage gates.
- [ ] Real self-hosted S3 test, concurrency and RQ duplicate delivery under multi-worker load.
- [ ] Actual managed rollout plan and operational instructions for a stuck `running` job.
- [ ] Backup/sanitized clone, production migration timing and rollback approval.
- [ ] Security review and approval to activate both multi-output and write-journal flags.

**Rollback caution:** downgrading to `0005` drops the write journal and lease columns. On a real installation, this destroys pending crash-recovery evidence. Never downgrade without preserving or reviewing journal rows first. This PR performs downgrade rehearsals only in isolated synthetic-data databases.

**Status:** development proposal; Draft PR only, not merged, not deployed and both feature flags remain disabled.
