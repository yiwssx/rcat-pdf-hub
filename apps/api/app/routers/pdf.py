import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.audit import audit_event
from app.config import get_settings
from app.db import get_db
from app.models import FileRecord, JobRecord
from app.observability import record_job, set_queue_depth
from app.policy import ensure_daily_job_quota
from app.queue import pdf_queue
from app.routers.jobs import serialize
from app.schemas import (
    JobOut,
    MergeRequest,
    OcrRequest,
    PageNumberRequest,
    RotateRequest,
    SingleFileRequest,
    SplitRequest,
    StampRequest,
    WatermarkRequest,
)
from app.security import Principal, require_scope

router = APIRouter(prefix="/api/v1/pdf", tags=["pdf"])
settings = get_settings()


def _is_expired(record: FileRecord) -> bool:
    if record.expires_at is None:
        return False
    expires_at = record.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at <= datetime.now(timezone.utc)


def _create_job(db: Session, principal: Principal, operation: str, file_ids: list[str], params: dict) -> JobOut:
    files = [db.get(FileRecord, fid) for fid in file_ids]
    if any(item is None for item in files):
        raise HTTPException(status_code=404, detail="One or more files not found")
    if any(_is_expired(item) for item in files if item):
        raise HTTPException(status_code=410, detail="One or more files have expired")
    if "*" not in principal.scopes and any(item.source_system != principal.name for item in files if item):
        raise HTTPException(status_code=403, detail="One or more files belong to another service")
    if not principal.is_bootstrap_admin:
        ensure_daily_job_quota(db, principal.name, principal.daily_job_limit)

    job = JobRecord(
        operation=operation,
        input_file_ids_json=json.dumps(file_ids),
        params_json=json.dumps(params, ensure_ascii=False),
        requested_by=principal.name,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    try:
        rq_job = pdf_queue.enqueue(
            "app.worker_tasks.process_job",
            job.id,
            job_timeout=settings.rq_job_timeout_seconds,
            result_ttl=86400,
        )
    except Exception as exc:
        job.status = "failed"
        job.progress = 100
        job.error = "Queue backend unavailable"
        job.finished_at = datetime.now(timezone.utc)
        db.commit()
        record_job(operation, "queue_failed")
        audit_event("job.queue_failed", principal.name, "job", job.id, {"operation": operation})
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Queue backend unavailable",
            headers={"Retry-After": "5"},
        ) from exc
    job.rq_job_id = rq_job.id
    db.commit()
    record_job(operation, "queued")
    set_queue_depth(settings.rq_queue, len(pdf_queue))
    audit_event("job.queued", principal.name, "job", job.id, {"operation": operation, "input_count": len(file_ids)})
    return serialize(job)


@router.post("/merge", response_model=JobOut, status_code=202)
def merge(req: MergeRequest, principal: Principal = Depends(require_scope("pdf:merge")), db: Session = Depends(get_db)):
    return _create_job(db, principal, "merge", req.file_ids, {})


@router.post("/split", response_model=JobOut, status_code=202)
def split(req: SplitRequest, principal: Principal = Depends(require_scope("pdf:split")), db: Session = Depends(get_db)):
    return _create_job(db, principal, "split", [req.file_id], {"pages": req.pages})


@router.post("/rotate", response_model=JobOut, status_code=202)
def rotate(req: RotateRequest, principal: Principal = Depends(require_scope("pdf:rotate")), db: Session = Depends(get_db)):
    if req.degrees not in {-270, -180, -90, 90, 180, 270}:
        raise HTTPException(status_code=422, detail="degrees must be one of ±90, ±180, ±270")
    return _create_job(db, principal, "rotate", [req.file_id], {"degrees": req.degrees, "pages": req.pages})


@router.post("/compress", response_model=JobOut, status_code=202)
def compress(req: SingleFileRequest, principal: Principal = Depends(require_scope("pdf:compress")), db: Session = Depends(get_db)):
    return _create_job(db, principal, "compress", [req.file_id], {})


@router.post("/ocr", response_model=JobOut, status_code=202)
def ocr(req: OcrRequest, principal: Principal = Depends(require_scope("pdf:ocr")), db: Session = Depends(get_db)):
    return _create_job(db, principal, "ocr", [req.file_id], req.model_dump(exclude={"file_id"}))


@router.post("/pdfa", response_model=JobOut, status_code=202)
def pdfa(req: OcrRequest, principal: Principal = Depends(require_scope("pdf:pdfa")), db: Session = Depends(get_db)):
    return _create_job(db, principal, "pdfa", [req.file_id], {"languages": req.languages})


@router.post("/office-to-pdf", response_model=JobOut, status_code=202)
def office_to_pdf(req: SingleFileRequest, principal: Principal = Depends(require_scope("pdf:convert")), db: Session = Depends(get_db)):
    return _create_job(db, principal, "office-to-pdf", [req.file_id], {})


@router.post("/watermark", response_model=JobOut, status_code=202)
def watermark(req: WatermarkRequest, principal: Principal = Depends(require_scope("pdf:watermark")), db: Session = Depends(get_db)):
    return _create_job(db, principal, "watermark", [req.file_id], req.model_dump(exclude={"file_id"}))


@router.post("/page-numbers", response_model=JobOut, status_code=202)
def page_numbers(req: PageNumberRequest, principal: Principal = Depends(require_scope("pdf:page-number")), db: Session = Depends(get_db)):
    return _create_job(db, principal, "page-numbers", [req.file_id], req.model_dump(exclude={"file_id"}))


@router.post("/stamp", response_model=JobOut, status_code=202)
def stamp(req: StampRequest, principal: Principal = Depends(require_scope("pdf:stamp")), db: Session = Depends(get_db)):
    if req.file_id == req.stamp_file_id:
        raise HTTPException(status_code=422, detail="Target and stamp files must be different")
    return _create_job(
        db,
        principal,
        "stamp",
        [req.file_id, req.stamp_file_id],
        req.model_dump(exclude={"file_id", "stamp_file_id"}),
    )
