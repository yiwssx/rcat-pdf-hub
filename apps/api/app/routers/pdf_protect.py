"""M09 authenticated PDF protection API: two passwords never reach job storage."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.audit import audit_event
from app.config import get_settings
from app.db import get_db
from app.models import FileRecord, JobRecord
from app.observability import record_job, set_queue_depth
from app.policy import ensure_daily_job_quota
from app.queue import enqueue_processing_job
from app.routers.jobs import serialize
from app.routers.pdf import _is_expired
from app.schemas import JobOut
from app.security import Principal, require_scope
from app.services.pdf_protect_handoff import (
    erase_credentials, publish_credentials, validate_credentials,
)
from app.services.pdf_unlock_handoff import valid_handoff_key

router = APIRouter(prefix="/api/v1/pdf", tags=["pdf (staged)"])
settings = get_settings()
MAX_REQUEST_BYTES = 4096
MAX_SOURCE_BYTES = 16 * 1024 * 1024


async def _read_credentials_request(request: Request) -> tuple[str, str, str]:
    """Parse without FastAPI 422 echoing request fields containing secrets."""
    if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != "application/json":
        raise HTTPException(status_code=415, detail="JSON request required")
    buffer = bytearray()
    async for chunk in request.stream():
        if len(buffer) + len(chunk) > MAX_REQUEST_BYTES:
            raise HTTPException(status_code=413, detail="M09 request too large")
        buffer.extend(chunk)
    try:
        data = json.loads(buffer)
    except (ValueError, UnicodeDecodeError):
        raise HTTPException(status_code=422, detail="Invalid M09 JSON payload") from None
    if not isinstance(data, dict) or set(data) != {"file_id", "user_password", "owner_password"}:
        raise HTTPException(status_code=422, detail="Expected file_id and two PDF passwords")
    file_id = data["file_id"]
    if not isinstance(file_id, str) or not 1 <= len(file_id) <= 36:
        raise HTTPException(status_code=422, detail="Invalid file reference")
    user_password, owner_password = data["user_password"], data["owner_password"]
    try:
        validate_credentials(user_password, owner_password)
    except (ValueError, TypeError):
        raise HTTPException(status_code=422, detail="Invalid PDF credentials") from None
    return file_id, user_password, owner_password


@router.post("/protect-pdf", response_model=JobOut, status_code=202)
async def protect_pdf_request(
    request: Request,
    principal: Principal = Depends(require_scope("pdf:protect")),
    db: Session = Depends(get_db),
) -> JobOut:
    if not settings.protect_pdf_tools_enabled:
        raise HTTPException(status_code=404, detail="M09 protection disabled")
    if not valid_handoff_key(settings.protect_pdf_handoff_key):
        raise HTTPException(status_code=503, detail="M09 handoff not configured")
    file_id, user_password, owner_password = await _read_credentials_request(request)
    record = db.get(FileRecord, file_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Source PDF not found")
    # Never allow wildcard/admin privileges to bypass user-owned sources here.
    if record.source_system != principal.name:
        raise HTTPException(status_code=403, detail="Source PDF belongs to another owner")
    if _is_expired(record):
        raise HTTPException(status_code=410, detail="Source PDF expired")
    if record.content_type != "application/pdf" or not record.original_name.lower().endswith(".pdf"):
        raise HTTPException(status_code=415, detail="PDF source required")
    if not 24 <= record.size <= MAX_SOURCE_BYTES:
        raise HTTPException(status_code=413, detail="Source PDF exceeds M09 limit")
    if not principal.is_bootstrap_admin:
        ensure_daily_job_quota(db, principal.name, principal.daily_job_limit)
    if not audit_event("job.m09_requested", principal.name, "file", file_id, {"operation": "protect-pdf"}):
        raise HTTPException(status_code=503, detail="M09 audit unavailable")

    # Zero password fields, ciphertext or tokens in durable job metadata.
    job = JobRecord(
        operation="protect-pdf",
        input_file_ids_json=json.dumps([file_id]),
        params_json="{}",
        requested_by=principal.name,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    try:
        publish_credentials(
            job.id, principal.name, file_id,
            user_password=user_password, owner_password=owner_password,
        )
        queue, queued = enqueue_processing_job("protect-pdf", job.id)
        job.rq_job_id = queued.id
        db.commit()
    except Exception:
        erase_credentials(job.id)
        db.rollback()
        db.refresh(job)
        job.status = "failed"
        job.progress = 100
        job.error = "M09 submission unavailable; resubmit passwords"
        job.finished_at = datetime.now(timezone.utc)
        db.commit()
        record_job("protect-pdf", "queue_failed")
        audit_event(
            "job.m09_submission_failed", principal.name, "job", job.id,
            {"operation": "protect-pdf"},
        )
        raise HTTPException(status_code=503, detail="M09 submission unavailable") from None
    record_job("protect-pdf", "queued")
    set_queue_depth(queue.name, len(queue))
    audit_event(
        "job.queued", principal.name, "job", job.id,
        {"operation": "protect-pdf", "queue": queue.name, "input_count": 1},
    )
    return serialize(job)
