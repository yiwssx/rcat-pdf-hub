import json
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, desc, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.audit import audit_event
from app.models import FileRecord, JobRecord, WebhookDelivery
from app.policy import ensure_daily_job_quota
from app.queue import enqueue_processing_job, redis_conn
from app.schemas import JobOut
from app.security import Principal, require_scope
from rq.command import send_stop_job_command
from rq.job import Job as RQJob

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])


def serialize(job: JobRecord) -> JobOut:
    return JobOut(
        id=job.id,
        operation=job.operation,
        status=job.status,
        progress=job.progress,
        input_file_ids=json.loads(job.input_file_ids_json),
        output_file_id=job.output_file_id,
        params=json.loads(job.params_json),
        error=job.error,
        requested_by=job.requested_by,
    )


OPERATION_SCOPES = {
    "merge": "pdf:merge", "organize": "pdf:split", "split": "pdf:split", "rotate": "pdf:rotate",
    "compress": "pdf:compress", "ocr": "pdf:ocr", "pdfa": "pdf:pdfa", "office-to-pdf": "pdf:convert",
    "watermark": "pdf:watermark", "page-numbers": "pdf:page-number", "stamp": "pdf:stamp",
    "images-to-pdf": "pdf:image-to-pdf", "pdf-to-images": "pdf:pdf-to-image",
}


def _must_filter_job_owner(principal: Principal) -> bool:
    # All identity/session principals must remain owner-scoped, even if a
    # legacy cookie or human Admin role carries wildcard scopes.
    # Privileged human cross-user visibility is available only through the
    # separately audited, minimized Admin triage endpoint.
    return principal.auth_source not in {"api_key", "bootstrap"} or "*" not in principal.scopes


def _owned_job(db: Session, job_id: str, principal: Principal) -> JobRecord:
    job = db.get(JobRecord, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if _must_filter_job_owner(principal) and job.requested_by != principal.name:
        raise HTTPException(status_code=403, detail="Job belongs to another service")
    return job


def _require_operation_scope(job: JobRecord, principal: Principal) -> None:
    required = OPERATION_SCOPES.get(job.operation)
    if required and "*" not in principal.scopes and required not in principal.scopes:
        raise HTTPException(status_code=403, detail=f"Missing scope: {required}")


@router.get("/{job_id}", response_model=JobOut)
def get_job(
    job_id: str,
    principal: Principal = Depends(require_scope("jobs:read")),
    db: Session = Depends(get_db),
):
    return serialize(_owned_job(db, job_id, principal))


@router.get("", response_model=list[JobOut])
def list_jobs(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=100000),
    mine: bool = Query(default=False),
    status: Literal["queued", "running", "completed", "failed", "cancelled"] | None = Query(default=None),
    principal: Principal = Depends(require_scope("jobs:read")),
    db: Session = Depends(get_db),
):
    # Explicit "mine" is required for a human My Jobs view, including admins.
    # Existing API clients retain their current default scope semantics.
    stmt = select(JobRecord)
    if mine or _must_filter_job_owner(principal):
        stmt = stmt.where(JobRecord.requested_by == principal.name)
    if status is not None:
        stmt = stmt.where(JobRecord.status == status)
    stmt = stmt.order_by(desc(JobRecord.created_at), desc(JobRecord.id)).offset(offset).limit(limit)
    return [serialize(job) for job in db.scalars(stmt).all()]


@router.post("/{job_id}/cancel", response_model=JobOut)
def cancel_job(
    job_id: str,
    principal: Principal = Depends(require_scope("jobs:manage")),
    db: Session = Depends(get_db),
):
    job = _owned_job(db, job_id, principal)
    if job.status not in {"queued", "running"}:
        raise HTTPException(status_code=409, detail="Only queued or running jobs can be cancelled")
    if not job.rq_job_id:
        raise HTTPException(status_code=409, detail="Queue job reference is missing")
    try:
        rq_job = RQJob.fetch(job.rq_job_id, connection=redis_conn)
        if job.status == "running":
            send_stop_job_command(redis_conn, rq_job.id)
        else:
            rq_job.cancel()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Unable to cancel queue job") from exc
    job.status = "cancelled"
    job.progress = 100
    job.error = "Cancelled by user"
    job.finished_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(job)
    audit_event("job.cancelled", principal.name, "job", job.id, {"operation": job.operation})
    return serialize(job)


@router.post("/{job_id}/retry", response_model=JobOut, status_code=202)
def retry_job(
    job_id: str,
    principal: Principal = Depends(require_scope("jobs:manage")),
    db: Session = Depends(get_db),
):
    source = _owned_job(db, job_id, principal)
    if source.status not in {"failed", "cancelled"}:
        raise HTTPException(status_code=409, detail="Only failed or cancelled jobs can be retried")
    _require_operation_scope(source, principal)
    file_ids = json.loads(source.input_file_ids_json)
    files = [db.get(FileRecord, file_id) for file_id in file_ids]
    if any(file is None for file in files):
        raise HTTPException(status_code=410, detail="One or more input files no longer exist")
    if not principal.is_bootstrap_admin:
        ensure_daily_job_quota(db, principal.name, principal.daily_job_limit)
    job = JobRecord(
        operation=source.operation,
        input_file_ids_json=source.input_file_ids_json,
        params_json=source.params_json,
        requested_by=principal.name,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    try:
        queue, queued = enqueue_processing_job(job.operation, job.id)
        job.rq_job_id = queued.id
        db.commit()
    except Exception as exc:
        job.status = "failed"
        job.progress = 100
        job.error = "Queue backend unavailable"
        job.finished_at = datetime.now(timezone.utc)
        db.commit()
        raise HTTPException(status_code=503, detail="Queue backend unavailable") from exc
    audit_event(
        "job.retried",
        principal.name,
        "job",
        job.id,
        {"source_job_id": source.id, "operation": job.operation, "queue": queue.name},
    )
    return serialize(job)


@router.delete("/terminal")
def clear_terminal_jobs(
    principal: Principal = Depends(require_scope("jobs:manage")),
    db: Session = Depends(get_db),
):
    statuses = ("completed", "failed", "cancelled")
    stmt = select(JobRecord).where(JobRecord.status.in_(statuses))
    if _must_filter_job_owner(principal):
        stmt = stmt.where(JobRecord.requested_by == principal.name)
    rows = db.scalars(stmt).all()
    job_ids = [job.id for job in rows]
    if job_ids:
        db.execute(delete(WebhookDelivery).where(WebhookDelivery.job_id.in_(job_ids)))
        for job in rows:
            db.delete(job)
        db.commit()
    audit_event("job.history_cleared", principal.name, "job", None, {"count": len(job_ids)})
    return {"deleted": len(job_ids)}
