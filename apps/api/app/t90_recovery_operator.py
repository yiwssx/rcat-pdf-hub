"""T90-0.10 supervised expired-lease recovery, never an automatic requeue.

Run as an operator from the controlled API environment. Inspect by default.
The --apply mode fails closed unless RQ proves the exact job is terminal and
the database lease epoch is the one inspected. It does not touch storage or
reassign leases, and retains all journal evidence for later reconciliation.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from typing import Callable

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import SessionLocal
from app.models import ArtifactWriteJournal, JobRecord

# No 'finished' here: finished RQ with an uncommitted DB state is ambiguous.
RQ_TERMINAL_FAILURES = frozenset({"failed", "stopped", "canceled"})


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _aware(when: datetime | None) -> datetime | None:
    if when is None:
        return None
    return when.replace(tzinfo=timezone.utc) if when.tzinfo is None else when.astimezone(timezone.utc)


def inspect_expired_leases(db: Session, *, limit: int = 50,
                           now: datetime | None = None) -> dict:
    if type(limit) is not int or not 1 <= limit <= 200:
        raise ValueError("limit must be from 1 to 200")
    moment = _aware(now or utcnow())
    rows = db.scalars(
        select(JobRecord).where(
            JobRecord.status == "running",
            JobRecord.lease_token.is_not(None),
            JobRecord.lease_expires_at.is_not(None),
            JobRecord.lease_expires_at <= moment,
        ).order_by(JobRecord.lease_expires_at, JobRecord.id).limit(limit + 1)
    ).all()
    candidates = [{
        "job_id": j.id,
        "epoch": j.lease_epoch,
        "expired_at": _aware(j.lease_expires_at).isoformat(),
        "rq_job_reference_present": bool(j.rq_job_id),
        "unresolved_writes": db.scalar(
            select(func.count()).select_from(ArtifactWriteJournal).where(
                ArtifactWriteJournal.job_id == j.id,
                ArtifactWriteJournal.lease_epoch == j.lease_epoch,
                ArtifactWriteJournal.state == "planned",
            )
        ),
    } for j in rows[:limit]]
    return {
        "dry_run": True, "auto_requeue": False, "auto_delete": False,
        "truncated": len(rows) > limit, "candidates": candidates,
    }


def recover_expired_lease(
    db: Session, job_id: str, *, expected_epoch: int,
    rq_status: Callable[[str], str | None], now: datetime | None = None,
) -> bool:
    """CAS terminalize only if external RQ status proves the worker stopped.

    The verifier is a dependency for unit tests. Real CLI always uses a fresh
    Redis-backed RQ job status. Missing queue metadata, inconsistent deadlines,
    revived/new attempts and Redis outages prevent recovery.
    """
    if type(expected_epoch) is not int or expected_epoch < 1:
        raise ValueError("Expected execution epoch must be a positive integer")
    moment = _aware(now or utcnow())
    job = db.get(JobRecord, job_id)
    if (
        job is None or job.status != "running"
        or not job.lease_token or not job.rq_job_id
        or job.lease_epoch != expected_epoch
        or (expiry := _aware(job.lease_expires_at)) is None
        or expiry > moment
    ):
        db.rollback()
        return False
    original_token = job.lease_token
    # The queue must prove the specific enqueued job has left execution.
    # Any failure or unknown status is treated as still potentially running.
    try:
        status = rq_status(job.rq_job_id)
    except Exception:
        db.rollback()
        return False
    if status is None or str(status).lower() not in RQ_TERMINAL_FAILURES:
        db.rollback()
        return False
    changed = db.execute(
        update(JobRecord).execution_options(synchronize_session=False)
        .where(
            JobRecord.id == job_id,
            JobRecord.status == "running",
            JobRecord.lease_token == original_token,
            JobRecord.lease_epoch == expected_epoch,
            JobRecord.lease_expires_at <= moment,
            JobRecord.rq_job_id == job.rq_job_id,
        )
        .values(
            status="failed", progress=100, finished_at=moment,
            error="Execution lease expired; queue job confirmed stopped; operator recovery",
            lease_token=None, lease_expires_at=None,
        )
    )
    if changed.rowcount != 1:
        db.rollback()
        return False
    db.execute(
        update(ArtifactWriteJournal)
        .execution_options(synchronize_session=False)
        .where(
            ArtifactWriteJournal.job_id == job_id,
            ArtifactWriteJournal.lease_token == original_token,
            ArtifactWriteJournal.lease_epoch == expected_epoch,
            ArtifactWriteJournal.state == "planned",
        )
        .values(state="needs_review", updated_at=moment)
    )
    db.commit()
    return True


def _redis_rq_status(rq_id: str) -> str | None:
    from rq.job import Job as RQJob
    from app.queue import redis_conn
    # Always fetch from Redis on this call; never trust a previous UI state.
    job = RQJob.fetch(rq_id, connection=redis_conn)
    return str(job.get_status(refresh=True))


def main() -> None:
    parser = argparse.ArgumentParser(description="Supervised, fail-closed T90 lease recovery")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--job-id")
    parser.add_argument("--epoch", type=int)
    args = parser.parse_args()
    settings = get_settings()
    if not settings.artifact_write_journal_enabled:
        parser.error("Write-journal feature flag is OFF; cannot inspect/recover execution leases")
    with SessionLocal() as db:
        if not args.apply:
            print(json.dumps(inspect_expired_leases(db, limit=args.limit),
                             ensure_ascii=False, indent=2))
            return
        if not args.job_id or args.epoch is None:
            parser.error("--apply requires --job-id and --epoch from a fresh inspection")
        result = recover_expired_lease(
            db, args.job_id, expected_epoch=args.epoch, rq_status=_redis_rq_status
        )
    print(json.dumps({
        "job_id": args.job_id,
        "recovered": result,
        "files_deleted": 0,
        "requeued": False,
        "requires_manual_artifact_review": result,
    }, ensure_ascii=False))
    if not result:
        parser.exit(2, "Recovery rejected: RQ/lease/epoch verification did not pass\n")


if __name__ == "__main__":
    main()
