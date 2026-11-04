"""M08 unlock: password in bounded HTTPS body; never persisted in job or RQ.

The API stores only AEAD ciphertext in Valkey (NX + five-minute expiry).
An authenticated Worker atomically consumes it by job ID and owner/source AAD.
"""
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
from app.services.pdf_access_control import _password
from app.services.pdf_unlock_handoff import (
    erase_password, publish_password, valid_handoff_key,
)

router = APIRouter(prefix="/api/v1/pdf", tags=["pdf (staged)"])
settings = get_settings()
MAX_REQUEST_BYTES = 4096
MAX_SOURCE_BYTES = 16 * 1024 * 1024


async def _read_password_request(request: Request) -> tuple[str, str]:
    """Reject invalid payloads without reflecting submitted secret in 422 errors."""
    if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != "application/json":
        raise HTTPException(status_code=415, detail="JSON request required")
    buffer = bytearray()
    async for chunk in request.stream():
        if len(buffer) + len(chunk) > MAX_REQUEST_BYTES:
            raise HTTPException(status_code=413, detail="M08 request too large")
        buffer.extend(chunk)
    try:
        data = json.loads(buffer)
    except (TypeError, ValueError, UnicodeDecodeError):
        raise HTTPException(status_code=422, detail="Invalid M08 JSON payload") from None
    if not isinstance(data, dict) or set(data) != {"file_id", "password"}:
        raise HTTPException(status_code=422, detail="Expected file_id and password only")
    file_id, password = data["file_id"], data["password"]
    if not isinstance(file_id, str) or not 1 <= len(file_id) <= 36:
        raise HTTPException(status_code=422, detail="Invalid file reference")
    try:
        _password(password, "password")
        if len(password.encode("utf-8")) > 1024:
            raise ValueError("Password outside byte budget")
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid or oversized PDF password") from None
    return file_id, password


@router.post("/unlock-pdf", response_model=JobOut, status_code=202)
async def unlock_pdf_request(
    request: Request,
    principal: Principal = Depends(require_scope("pdf:unlock")),
    db: Session = Depends(get_db),
) -> JobOut:
    if not settings.unlock_pdf_tools_enabled:
        raise HTTPException(status_code=404, detail="M08 unlock is disabled")
    if not valid_handoff_key(settings.unlock_pdf_handoff_key):
        raise HTTPException(status_code=503, detail="M08 secret handoff not configured")
    file_id, password = await _read_password_request(request)
    record = db.get(FileRecord, file_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Source PDF not found")
    # Never grant a wildcard/admin cross-tenant exception here.
    if record.source_system != principal.name:
        raise HTTPException(status_code=403, detail="Source PDF belongs to another owner")
    if _is_expired(record):
        raise HTTPException(status_code=410, detail="Source PDF expired")
    if (record.content_type != "application/pdf"
            or not record.original_name.lower().endswith(".pdf")):
        raise HTTPException(status_code=415, detail="PDF source required")
    if not 24 <= record.size <= MAX_SOURCE_BYTES:
        raise HTTPException(status_code=413, detail="Source PDF exceeds M08 limit")
    if not principal.is_bootstrap_admin:
        ensure_daily_job_quota(db, principal.name, principal.daily_job_limit)
    if not audit_event("job.m08_requested", principal.name, "file", file_id, {"operation": "unlock-pdf"}):
        raise HTTPException(status_code=503, detail="M08 audit unavailable")

    # Deliberately NO password, encrypted password, token or reference in params.
    job = JobRecord(
        operation="unlock-pdf",
        input_file_ids_json=json.dumps([file_id]),
        params_json="{}",
        requested_by=principal.name,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    try:
        publish_password(job.id, principal.name, file_id, password)
        queue, rq_job = enqueue_processing_job("unlock-pdf", job.id)
        job.rq_job_id = rq_job.id
        db.commit()
    except Exception:
        erase_password(job.id)
        db.rollback()
        db.refresh(job)
        job.status = "failed"
        job.progress = 100
        job.error = "M08 submission unavailable; resubmit password"
        job.finished_at = datetime.now(timezone.utc)
        db.commit()
        record_job("unlock-pdf", "queue_failed")
        audit_event("job.m08_submission_failed", principal.name, "job", job.id, {"operation": "unlock-pdf"})
        raise HTTPException(status_code=503, detail="M08 submission unavailable") from None

    record_job("unlock-pdf", "queued")
    set_queue_depth(queue.name, len(queue))
    audit_event(
        "job.queued", principal.name, "job", job.id,
        {"operation": "unlock-pdf", "queue": queue.name, "input_count": 1},
    )
    # Request body, password and AEAD ciphertext are not returned to browser.
    return serialize(job)
