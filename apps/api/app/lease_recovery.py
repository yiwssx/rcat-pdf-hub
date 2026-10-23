"""Explicit, audited recovery of an expired attempt after RQ reports terminal.

No automatic lease takeover, requeue, object deletion, or URL exposure.
The operator must independently verify RQ status and request --apply with
the observed epoch. A stale process cannot subsequently publish outputs.
"""
from __future__ import annotations

import argparse
import json
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.audit import audit_event
from app.config import get_settings
from app.db import SessionLocal
from app.models import ArtifactWriteJournal, JobRecord

TERMINAL_RQ_STATUSES = frozenset({"failed", "stopped", "canceled"})


def _utc(value: datetime) -> datetime:
    # SQLite stores the project's UTC datetimes without TZ info.
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def inspect_or_recover_expired_job(
    db: Session, *,
    job_id: str, expected_epoch: int, rq_job,
    actor: str, apply: bool = False,
    now: datetime | None = None, grace_seconds: int = 300,
) -> dict:
    """Manual recovery gate, never a silent background task.

    The RQ job must be fetched live by the caller; stale/cached/provided
    string status is not sufficient evidence. Status is refreshed here.
    """
    if not actor.strip() or expected_epoch < 1:
        raise ValueError("Operator and positive expected epoch are required")
    if grace_seconds < 60:
        raise ValueError("Recovery grace must be at least 60 seconds")
    now = _utc(now or datetime.now(timezone.utc))
    job = db.get(JobRecord, job_id)
    if job is None or not job.lease_token or job.lease_epoch != expected_epoch:
        raise ValueError("Job or execution epoch is not current")
    if job.status != "running" or job.output_file_id is not None:
        raise ValueError("Only incomplete running attempts are recoverable")
    if job.lease_expires_at is None or _utc(job.lease_expires_at) > now - timedelta(seconds=grace_seconds):
        raise ValueError("Lease has not expired beyond the required grace period")
    if not job.rq_job_id or rq_job.id != job.rq_job_id:
        raise ValueError("Original RQ job evidence does not match")
    if getattr(rq_job, "func_name", None) != "app.worker_tasks.process_job" or tuple(rq_job.args) != (job.id,):
        raise ValueError("RQ job invocation is not the expected worker task")
    status = rq_job.get_status(refresh=True)
    status = getattr(status, "value", status)
    if status not in TERMINAL_RQ_STATUSES:
        raise ValueError("RQ job is not verifiably terminal")
    linked = db.scalar(select(ArtifactWriteJournal.id).where(
        ArtifactWriteJournal.job_id == job.id,
        ArtifactWriteJournal.lease_epoch == expected_epoch,
        ArtifactWriteJournal.state == "committed",
    ))
    if linked:
        raise ValueError("Journal contains a committed artifact; manual investigation required")
    report = {
        "job_id": job.id, "observed_epoch": expected_epoch,
        "rq_status": status, "expired": True,
        "dry_run": not apply, "auto_requeued": False, "auto_deleted": False,
        "action": "mark_failed_no_retry" if apply else "eligible_for_operator_review",
    }
    if not apply:
        return report
    if not audit_event(
        "job.lease_recovery_requested", actor, "job", job.id,
        {"epoch": expected_epoch, "rq_status": status},
    ):
        raise RuntimeError("Audit log unavailable; refusing recovery")
    token = job.lease_token
    changed = db.execute(
        update(JobRecord).execution_options(synchronize_session=False).where(
            JobRecord.id == job.id,
            JobRecord.status == "running",
            JobRecord.lease_token == token,
            JobRecord.lease_epoch == expected_epoch,
            JobRecord.rq_job_id == rq_job.id,
            JobRecord.output_file_id.is_(None),
            JobRecord.lease_expires_at <= now - timedelta(seconds=grace_seconds),
        ).values(
            status="failed", progress=100, lease_token=None,
            finished_at=now,
            error="Execution lease expired and RQ was terminal; manual retry required",
        )
    )
    if changed.rowcount != 1:
        db.rollback()
        raise RuntimeError("Job changed during recovery; no update applied")
    db.commit()
    audit_event(
        "job.lease_recovered", actor, "job", job.id,
        {"epoch": expected_epoch, "rq_status": status, "cleanup": "not_attempted"},
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Inspect or manually quarantine expired fenced jobs; never deletes files or retries."
    )
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--expected-epoch", type=int, required=True)
    parser.add_argument("--operator", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    uuid.UUID(args.job_id)
    if not get_settings().artifact_write_journal_enabled:
        parser.error("Enable the journaled worker only after migration and sign-off")
    from rq.job import Job as RQJob
    from app.queue import redis_conn

    with SessionLocal() as db:
        job = db.get(JobRecord, args.job_id)
        if job is None or not job.rq_job_id:
            parser.error("No verified queue reference found for job")
        # Fail closed if Redis/RQ cannot be queried or the job has expired.
        rq_job = RQJob.fetch(job.rq_job_id, connection=redis_conn)
        report = inspect_or_recover_expired_job(
            db, job_id=args.job_id, expected_epoch=args.expected_epoch,
            rq_job=rq_job, actor=args.operator, apply=args.apply,
            grace_seconds=get_settings().lease_recovery_grace_seconds,
        )
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
