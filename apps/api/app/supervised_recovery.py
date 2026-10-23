"""Supervised, fenced recovery for abandoned T90 write-journal jobs.

Read-only by default. Quarantine requires explicit exact epoch/token, an
expired lease, a verifiably TERMINAL RQ job and a successfully written audit
entry. Never requeue, take over a lease, or delete any artifact automatically.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.audit import audit_event
from app.db import SessionLocal
from app.models import ArtifactWriteJournal, JobOutputArtifact, JobRecord

TERMINAL_RQ_STATUSES = frozenset({"failed", "stopped", "canceled", "finished"})
MAX_ITEMS = 100


def _now():
    return datetime.now(timezone.utc)


def _normalized(moment: datetime) -> datetime:
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise ValueError("A timezone-aware timestamp is required")
    return moment.astimezone(timezone.utc)


def inspect_stale_leases(db: Session, *, now: datetime | None = None, limit: int = 50) -> dict:
    """Inventory potential abandoned jobs. Does not touch RQ, status, or blobs."""
    if type(limit) is not int or not 1 <= limit <= MAX_ITEMS:
        raise ValueError("limit must be 1..100")
    moment = _normalized(now or _now())
    jobs = db.scalars(
        select(JobRecord)
        .where(
            JobRecord.status == "running",
            JobRecord.lease_token.is_not(None),
            JobRecord.lease_expires_at.is_not(None),
            JobRecord.lease_expires_at <= moment,
        )
        .order_by(JobRecord.lease_expires_at.asc(), JobRecord.id.asc())
        .limit(limit + 1)
    ).all()
    candidates = []
    for job in jobs[:limit]:
        unresolved = db.scalars(
            select(ArtifactWriteJournal.state).where(
                ArtifactWriteJournal.job_id == job.id,
                ArtifactWriteJournal.lease_token == job.lease_token,
                ArtifactWriteJournal.state.in_(("planned", "needs_review")),
            )
        ).all()
        candidates.append({
            "job_id": job.id,
            "lease_epoch": job.lease_epoch,
            "lease_token": job.lease_token,
            "rq_job_present": bool(job.rq_job_id),
            "expired_seconds": max(0, int(
                (moment - _normalized(job.lease_expires_at.replace(tzinfo=timezone.utc)
                    if job.lease_expires_at.tzinfo is None else job.lease_expires_at)
                ).total_seconds()
            )),
            "unresolved_journal_count": len(unresolved),
        })
    return {
        "dry_run": True, "mutated": False, "scanned": len(jobs[:limit]),
        "truncated": len(jobs) > limit, "candidates": candidates,
    }


def _verified_rq_state(rq_job_id: str) -> str:
    # Fetch only inside the mutation path. Redis errors are fatal and prevent
    # quarantine; stale or missing RQ metadata is not evidence of termination.
    from rq.job import Job as RQJob
    from app.queue import redis_conn

    rq_job = RQJob.fetch(rq_job_id, connection=redis_conn)
    status = rq_job.get_status(refresh=True)
    return str(getattr(status, "value", status)).lower()


def quarantine_expired_job(
    db: Session, job_id: str, *, expected_token: str,
    expected_epoch: int, now: datetime | None = None,
) -> bool:
    """Manual, audited CAS: mark abandoned job failed, never requeue/delete.

    The caller MUST provide the exact token and epoch from the read-only
    inventory. This function checks RQ itself; RQ status cannot be supplied
    by an HTTP client or CLI flag. A task that is still running, whose RQ
    state cannot be verified, or whose result was published is fail-closed.
    """
    moment = _normalized(now or _now())
    if not expected_token or type(expected_epoch) is not int or expected_epoch < 1:
        raise ValueError("Exact valid lease token and epoch required")

    job = db.get(JobRecord, job_id)
    if (
        job is None or job.status != "running" or
        job.lease_token != expected_token or
        job.lease_epoch != expected_epoch or
        job.lease_expires_at is None or
        _normalized(
            job.lease_expires_at.replace(tzinfo=timezone.utc)
            if job.lease_expires_at.tzinfo is None else job.lease_expires_at
        ) > moment or
        not job.rq_job_id or job.output_file_id is not None
    ):
        return False
    if db.scalar(select(JobOutputArtifact.job_id).where(
        JobOutputArtifact.job_id == job_id
    ).limit(1)) is not None:
        return False

    rq_status = _verified_rq_state(job.rq_job_id)
    if rq_status not in TERMINAL_RQ_STATUSES:
        raise RuntimeError("RQ job is not verifiably terminal; no changes made")
    if not audit_event(
        "job.stale_lease_quarantine_requested", "t90-operator", "job", job.id,
        {"lease_epoch": expected_epoch, "rq_status": rq_status},
    ):
        raise RuntimeError("Recovery audit unavailable; no changes made")

    # A competing heartbeat, completion, cancellation or another operator
    # invalidates the predicate; only ONE operator may quarantine a job.
    changed = db.execute(
        update(JobRecord)
        .execution_options(synchronize_session=False)
        .where(
            JobRecord.id == job_id,
            JobRecord.status == "running",
            JobRecord.lease_token == expected_token,
            JobRecord.lease_epoch == expected_epoch,
            JobRecord.lease_expires_at <= moment,
            JobRecord.output_file_id.is_(None),
        )
        .values(
            status="failed",
            progress=100,
            error="Operator-quarantined expired execution lease; inspect artifact write journal",
            finished_at=moment,
            lease_token=None,
            lease_epoch=JobRecord.lease_epoch + 1,
        )
    )
    if changed.rowcount != 1:
        db.rollback()
        return False
    db.commit()
    return True


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Inspect stale worker leases; explicit RQ-verified quarantine only."
    )
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--quarantine-job-id")
    parser.add_argument("--expected-token")
    parser.add_argument("--expected-epoch", type=int)
    parser.add_argument(
        "--acknowledge", default="",
        help="Required literal 'quarantine-without-requeue-or-delete' for mutation",
    )
    args = parser.parse_args()
    with SessionLocal() as db:
        if not args.quarantine_job_id:
            if args.expected_token or args.expected_epoch or args.acknowledge:
                parser.error("No mutation arguments allowed during read-only inventory")
            print(json.dumps(inspect_stale_leases(db, limit=args.limit), indent=2))
            return
        if (
            args.acknowledge != "quarantine-without-requeue-or-delete" or
            not args.expected_token or args.expected_epoch is None
        ):
            parser.error("Quarantine requires matching token, epoch and explicit acknowledgment")
        result = quarantine_expired_job(
            db, args.quarantine_job_id, expected_token=args.expected_token,
            expected_epoch=args.expected_epoch,
        )
        print(json.dumps({
            "job_id": args.quarantine_job_id, "quarantined": result,
            "auto_requeue": False, "deleted_artifacts": False,
        }))


if __name__ == "__main__":
    main()
