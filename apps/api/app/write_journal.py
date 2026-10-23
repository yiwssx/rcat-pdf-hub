"""Opt-in fenced job execution and pre-write storage intentions.

A lease is CLAIM-ONCE. Expired or running jobs are *not* auto-taken over:
that needs a separate durable heartbeat/recovery decision. All mutations
that could publish outputs are protected by the same token+deadline.
"""
import uuid
from threading import Event, Thread
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models import ArtifactWriteJournal, JobRecord


def utcnow():
    return datetime.now(timezone.utc)


def claim_queued_job(db: Session, job: JobRecord, ttl_seconds: int) -> str | None:
    if ttl_seconds < 60:
        raise ValueError("Execution lease must exceed 60 seconds")
    token = str(uuid.uuid4())
    now = utcnow()
    result = db.execute(
        update(JobRecord)
        .execution_options(synchronize_session=False)
        .where(JobRecord.id == job.id, JobRecord.status == "queued")
        .values(
            status="running", progress=10, started_at=now, error=None,
            lease_token=token, lease_epoch=JobRecord.lease_epoch + 1,
            lease_expires_at=now + timedelta(seconds=ttl_seconds),
        )
    )
    if result.rowcount != 1:
        db.rollback()
        return None
    db.commit()
    db.refresh(job)
    return token


def renew_lease(
    db: Session, job_id: str, lease_token: str, lease_epoch: int,
    ttl_seconds: int,
) -> bool:
    """Conditional heartbeat from a separate DB session, never resurrecting a job.

    Do not renew an expired lease, cancelled/finished job, or a changed
    attempt. The DB compares the deadline (SQL, not ORM timezone evaluation).
    """
    if ttl_seconds < 60:
        raise ValueError("Execution lease must exceed 60 seconds")
    now = utcnow()
    result = db.execute(
        update(JobRecord)
        .execution_options(synchronize_session=False)
        .where(
            JobRecord.id == job_id,
            JobRecord.status == "running",
            JobRecord.lease_token == lease_token,
            JobRecord.lease_epoch == lease_epoch,
            JobRecord.lease_expires_at > now,
        )
        .values(lease_expires_at=now + timedelta(seconds=ttl_seconds))
    )
    if result.rowcount != 1:
        db.rollback()
        return False
    db.commit()
    return True


def fenced_progress(db: Session, job: JobRecord, token: str, progress: int) -> None:
    result = db.execute(
        update(JobRecord)
        .execution_options(synchronize_session=False)
        .where(
            JobRecord.id == job.id, JobRecord.status == "running",
            JobRecord.lease_token == token,
            JobRecord.lease_expires_at > utcnow(),
        )
        .values(progress=progress)
    )
    if result.rowcount != 1:
        db.rollback()
        raise RuntimeError("Job execution lease is no longer valid")
    db.commit()
    db.refresh(job)


def lease_is_current(db: Session, job: JobRecord, token: str) -> bool:
    return db.scalar(
        select(JobRecord.id).where(
            JobRecord.id == job.id, JobRecord.status == "running",
            JobRecord.lease_token == token,
            JobRecord.lease_expires_at > utcnow(),
        )
    ) is not None


def reserve_writes(db: Session, job: JobRecord, token: str, specs: list[tuple[str, str]]) -> None:
    if not lease_is_current(db, job, token):
        raise RuntimeError("Job execution lease expired before reserving writes")
    if not specs or len(set(name for name, _ in specs)) != len(specs):
        raise ValueError("Duplicate/empty artifact write plan")
    for stored_name, role in specs:
        db.add(ArtifactWriteJournal(
            id=str(uuid.uuid4()), job_id=job.id,
            lease_epoch=job.lease_epoch, lease_token=token,
            stored_name=stored_name, role=role, state="planned",
        ))
    # Durable COMMIT BEFORE the first write. Do not call after adding staged
    # FileRecords, which must remain atomic with Job completion.
    db.commit()


def mark_committed(db: Session, job: JobRecord, token: str, names_to_files: dict[str, str]) -> None:
    for stored_name, file_id in names_to_files.items():
        result = db.execute(
            update(ArtifactWriteJournal)
            .where(
                ArtifactWriteJournal.job_id == job.id,
                ArtifactWriteJournal.lease_token == token,
                ArtifactWriteJournal.stored_name == stored_name,
                ArtifactWriteJournal.state == "planned",
            )
            .values(state="committed", file_id=file_id, updated_at=utcnow())
        )
        if result.rowcount != 1:
            raise RuntimeError("Write journal is missing or already finalized")
    # Caller commits journal transitions with FileRecords and Job completion.


def compensate_writes(
    db: Session, job: JobRecord, token: str, results: dict[str, bool]
) -> None:
    """Mark every planned write 'compensated' or 'needs_review'.

    True means the storage delete confirmed or the destination did not
    exist. False means cleanup failed or its outcome is unknown. This
    method NEVER deletes data; callers may perform best-effort deletion
    before invoking it.
    """
    for row in db.scalars(select(ArtifactWriteJournal).where(
        ArtifactWriteJournal.job_id == job.id,
        ArtifactWriteJournal.lease_token == token,
        ArtifactWriteJournal.state == "planned",
    )).all():
        row.state = "compensated" if results.get(row.stored_name) else "needs_review"
        row.updated_at = utcnow()
    db.commit()


def renew_execution_lease(
    db: Session, job_id: str, token: str, ttl_seconds: int,
    *, now: datetime | None = None,
) -> bool:
    """CAS heartbeat: only the live owner can extend an unexpired lease.

    A failed/stale/cancelled worker cannot revive or acquire an expired job.
    Use a dedicated database Session; never share the processing Session
    across worker and heartbeat threads.
    """
    if ttl_seconds < 60:
        raise ValueError("Execution lease must exceed 60 seconds")
    moment = now or utcnow()
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise ValueError("Heartbeat timestamp must be timezone-aware")
    changed = db.execute(
        update(JobRecord)
        .execution_options(synchronize_session=False)
        .where(
            JobRecord.id == job_id,
            JobRecord.status == "running",
            JobRecord.lease_token == token,
            JobRecord.lease_expires_at > moment,
        )
        .values(lease_expires_at=moment + timedelta(seconds=ttl_seconds))
    )
    if changed.rowcount != 1:
        db.rollback()
        return False
    db.commit()
    return True


class LeaseHeartbeat:
    """Daemon heartbeat with a separate transaction per renewal.

    Temporary database errors are retried on the next tick. A definitive
    CAS rejection sets lost; all publishing remains fenced in SQL.
    No self-requeue, force termination, or automatic lease takeover.
    """

    def __init__(self, session_factory, job_id: str, token: str,
                 ttl_seconds: int, interval_seconds: float):
        if interval_seconds <= 0 or interval_seconds >= ttl_seconds / 3:
            raise ValueError("Heartbeat cadence must be positive and under one third of lease TTL")
        self.session_factory = session_factory
        self.job_id = job_id
        self.token = token
        self.ttl_seconds = ttl_seconds
        self.interval_seconds = interval_seconds
        self._stop = Event()
        self.lost = Event()
        self._thread = Thread(
            target=self._run, name="pdfhub-lease-heartbeat", daemon=True
        )

    def start(self):
        self._thread.start()
        return self

    def _run(self):
        while not self._stop.wait(self.interval_seconds):
            try:
                with self.session_factory() as db:
                    if not renew_execution_lease(
                        db, self.job_id, self.token, self.ttl_seconds
                    ):
                        self.lost.set()
                        return
            except Exception:
                # The next heartbeat may succeed. The final fenced SQL
                # transition will reject an actually expired lease.
                continue

    def stop(self) -> None:
        self._stop.set()
        if self._thread.is_alive():
            self._thread.join(timeout=10)

