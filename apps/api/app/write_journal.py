"""Opt-in fenced job execution and pre-write storage intentions.

A lease is CLAIM-ONCE. Expired or running jobs are *not* auto-taken over:
that needs a separate durable heartbeat/recovery decision. All mutations
that could publish outputs are protected by the same token+deadline.
"""
import uuid
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


def fenced_progress(db: Session, job: JobRecord, token: str, progress: int) -> None:
    result = db.execute(
        update(JobRecord)
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
