from datetime import datetime, timedelta, timezone

from rq.exceptions import NoSuchJobError
from rq.job import Job
from sqlalchemy import select

from app.audit import audit_event
from app.config import get_settings
from app.db import SessionLocal
from app.models import JobRecord
from app.queue import redis_conn

settings = get_settings()
QUEUE_MISSING_GRACE_SECONDS = 300
RUNNING_GRACE_SECONDS = 300


def _aware(value):
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _rq_status(job: Job) -> str:
    value = job.get_status(refresh=True)
    raw = getattr(value, "value", value)
    return str(raw).lower()


def reconcile_stale_jobs_once() -> dict[str, int]:
    """Reconcile DB job state with RQ after worker crashes or hard timeouts."""
    now = datetime.now(timezone.utc)
    queue_missing_cutoff = now - timedelta(seconds=QUEUE_MISSING_GRACE_SECONDS)
    running_cutoff = now - timedelta(seconds=settings.rq_job_timeout_seconds + RUNNING_GRACE_SECONDS)
    inspected = 0
    failed = 0

    with SessionLocal() as db:
        rows = db.scalars(
            select(JobRecord)
            .where(JobRecord.status.in_(("queued", "running")))
            .order_by(JobRecord.created_at)
            .limit(1000)
        ).all()
        for record in rows:
            inspected += 1
            created_at = _aware(record.created_at) or now
            started_at = _aware(record.started_at)
            reason: str | None = None

            if record.status == "running" and started_at and started_at <= running_cutoff:
                reason = "Worker execution exceeded timeout plus reconciliation grace period"
            elif not record.rq_job_id:
                if created_at <= queue_missing_cutoff:
                    reason = "Queued job has no RQ job id after reconciliation grace period"
            else:
                try:
                    rq_job = Job.fetch(record.rq_job_id, connection=redis_conn)
                    rq_status = _rq_status(rq_job)
                except NoSuchJobError:
                    if created_at <= queue_missing_cutoff:
                        reason = "RQ job no longer exists"
                except Exception:
                    # Redis/RQ availability is handled by readiness. Do not mutate DB state
                    # when reconciliation cannot establish the queue state reliably.
                    continue
                else:
                    if rq_status in {"failed", "stopped", "canceled", "cancelled"}:
                        reason = f"RQ job is terminal without DB completion ({rq_status})"
                    elif rq_status == "finished" and record.status != "completed":
                        reason = "RQ job finished without a completed DB record"

            if reason:
                record.status = "failed"
                record.progress = 100
                record.error = reason
                record.finished_at = now
                failed += 1
                audit_event(
                    "job.reconciled_failed",
                    "reconciler",
                    "job",
                    record.id,
                    {"reason": reason, "rq_job_id": record.rq_job_id},
                )
        db.commit()

    return {"inspected": inspected, "reconciled_failed": failed}
