"""T90-2 opt-in format-specific routes, absent from default OpenAPI."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import FileRecord
from app.routers.pdf import _create_job, _is_expired
from app.schemas import JobOut
from app.security import Principal, require_scope
from app.staged_to_pdf_adapters import STAGED_TO_PDF_INPUTS

router = APIRouter(prefix="/api/v1/pdf/to-pdf", tags=["T90-2 (staged)"])
settings = get_settings()


class ConvertRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    file_id: str = Field(min_length=1, max_length=36)


def _submit(req: ConvertRequest, principal: Principal, db: Session, operation: str) -> JobOut:
    if not settings.to_pdf_tools_enabled:
        raise HTTPException(status_code=404, detail="Staged conversion is disabled")
    record = db.get(FileRecord, req.file_id)
    if record is None:
        raise HTTPException(status_code=404, detail="File not found")
    if record.source_system != principal.name:
        raise HTTPException(status_code=403, detail="File belongs to another owner")
    if _is_expired(record):
        raise HTTPException(status_code=410, detail="File data has expired")
    mime, suffix = STAGED_TO_PDF_INPUTS[operation]
    extensions = (".tif", ".tiff") if suffix == ".tiff" else (suffix,)
    if record.content_type != mime or not record.original_name.lower().endswith(extensions):
        raise HTTPException(status_code=415, detail="Uploaded format does not match conversion")
    return _create_job(db, principal, operation, [req.file_id], {})


@router.post("/txt", response_model=JobOut, status_code=202)
def txt_to_pdf(req: ConvertRequest, principal: Principal = Depends(require_scope("pdf:convert")),
               db: Session = Depends(get_db)):
    return _submit(req, principal, db, "txt-to-pdf")


@router.post("/csv", response_model=JobOut, status_code=202)
def csv_to_pdf(req: ConvertRequest, principal: Principal = Depends(require_scope("pdf:convert")),
               db: Session = Depends(get_db)):
    return _submit(req, principal, db, "csv-to-pdf")


@router.post("/jfif", response_model=JobOut, status_code=202)
def jfif_to_pdf(req: ConvertRequest, principal: Principal = Depends(require_scope("pdf:image-to-pdf")),
                db: Session = Depends(get_db)):
    return _submit(req, principal, db, "jfif-to-pdf")


@router.post("/gif", response_model=JobOut, status_code=202)
def gif_to_pdf(req: ConvertRequest, principal: Principal = Depends(require_scope("pdf:image-to-pdf")),
               db: Session = Depends(get_db)):
    return _submit(req, principal, db, "gif-to-pdf")


@router.post("/tiff", response_model=JobOut, status_code=202)
def tiff_to_pdf(req: ConvertRequest, principal: Principal = Depends(require_scope("pdf:image-to-pdf")),
                db: Session = Depends(get_db)):
    return _submit(req, principal, db, "tiff-to-pdf")
