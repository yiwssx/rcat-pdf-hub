import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import FileRecord, JobRecord
from app.queue import pdf_queue
from app.schemas import JobOut, MergeRequest, OcrRequest, RotateRequest, SingleFileRequest, SplitRequest
from app.security import Principal, require_scope
from app.routers.jobs import serialize

router = APIRouter(prefix="/api/v1/pdf", tags=["pdf"])


def _create_job(db: Session, principal: Principal, operation: str, file_ids: list[str], params: dict) -> JobOut:
    files = [db.get(FileRecord, fid) for fid in file_ids]
    if any(item is None for item in files):
        raise HTTPException(status_code=404, detail="One or more files not found")
    if "*" not in principal.scopes and any(item.source_system != principal.name for item in files if item):
        raise HTTPException(status_code=403, detail="One or more files belong to another service")
    job = JobRecord(
        operation=operation,
        input_file_ids_json=json.dumps(file_ids),
        params_json=json.dumps(params),
        requested_by=principal.name,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    rq_job = pdf_queue.enqueue("app.worker_tasks.process_job", job.id, job_timeout=1800, result_ttl=86400)
    job.rq_job_id = rq_job.id
    db.commit()
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
