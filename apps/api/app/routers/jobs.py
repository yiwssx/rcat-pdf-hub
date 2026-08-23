import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import JobRecord
from app.schemas import JobOut
from app.security import Principal, require_scope

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


@router.get("/{job_id}", response_model=JobOut)
def get_job(
    job_id: str,
    principal: Principal = Depends(require_scope("jobs:read")),
    db: Session = Depends(get_db),
):
    job = db.get(JobRecord, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if "*" not in principal.scopes and job.requested_by != principal.name:
        raise HTTPException(status_code=403, detail="Job belongs to another service")
    return serialize(job)


@router.get("", response_model=list[JobOut])
def list_jobs(
    limit: int = Query(default=20, ge=1, le=100),
    principal: Principal = Depends(require_scope("jobs:read")),
    db: Session = Depends(get_db),
):
    stmt = select(JobRecord).order_by(desc(JobRecord.created_at)).limit(limit)
    if "*" not in principal.scopes:
        stmt = stmt.where(JobRecord.requested_by == principal.name)
    return [serialize(job) for job in db.scalars(stmt).all()]
