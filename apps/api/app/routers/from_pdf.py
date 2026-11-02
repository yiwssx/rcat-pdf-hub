"""T90-3 F09 staging-only endpoint: PDF -> true multipage TIFF.

Never loaded into the public OpenAPI schema until independently opted in.
All queue jobs use the existing owner, quota, audit and retention contracts.
"""
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
from app.services.from_pdf_tiff import MAX_SOURCE_BYTES

router = APIRouter(prefix="/api/v1/pdf/from-pdf", tags=["from-pdf (staged)"])
settings = get_settings()


class PdfToTiffRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    file_id: str = Field(min_length=1, max_length=36)
    dpi: int = Field(default=150, strict=True, ge=72, le=300)


@router.post("/tiff", status_code=202, response_model=JobOut)
def pdf_to_tiff(
    req: PdfToTiffRequest,
    principal: Principal = Depends(require_scope("pdf:pdf-to-image")),
    db: Session = Depends(get_db),
):
    if not settings.from_pdf_tools_enabled:
        raise HTTPException(status_code=404, detail="T90-3 conversion is disabled")
    source = db.get(FileRecord, req.file_id)
    if source is None:
        raise HTTPException(status_code=404, detail="File not found")
    # Staged tools are intentionally stricter than bootstrap-admin legacy flows.
    if source.source_system != principal.name:
        raise HTTPException(status_code=403, detail="File is owned by a different account")
    if _is_expired(source):
        raise HTTPException(status_code=410, detail="PDF has expired")
    if (source.content_type != "application/pdf"
            or not source.original_name.lower().endswith(".pdf")):
        raise HTTPException(status_code=415, detail="A verified PDF source is required")
    if not 16 <= source.size <= MAX_SOURCE_BYTES:
        raise HTTPException(status_code=413, detail="PDF exceeds TIFF conversion budget")
    return _create_job(db, principal, "pdf-to-tiff", [req.file_id], {"dpi": req.dpi})


class PdfToGifRequest(BaseModel):
    """F16 animation: every PDF page is one 256-color GIF frame."""
    model_config = ConfigDict(extra="forbid")
    file_id: str = Field(min_length=1, max_length=36)
    dpi: int = Field(default=96, strict=True, ge=72, le=150)
    frame_ms: int = Field(default=1200, strict=True, ge=300, le=5000)


@router.post("/gif", status_code=202, response_model=JobOut)
def pdf_to_gif(
    req: PdfToGifRequest,
    principal: Principal = Depends(require_scope("pdf:pdf-to-image")),
    db: Session = Depends(get_db),
):
    if not settings.from_pdf_tools_enabled:
        raise HTTPException(status_code=404, detail="T90-3 conversion is disabled")
    source = db.get(FileRecord, req.file_id)
    if source is None:
        raise HTTPException(status_code=404, detail="File not found")
    if source.source_system != principal.name:
        raise HTTPException(status_code=403, detail="File belongs to another account")
    if _is_expired(source):
        raise HTTPException(status_code=410, detail="Source PDF has expired")
    if (source.content_type != "application/pdf"
            or not source.original_name.lower().endswith(".pdf")):
        raise HTTPException(status_code=415, detail="A verified PDF source is required")
    if not 24 <= source.size <= MAX_SOURCE_BYTES:
        raise HTTPException(status_code=413, detail="Source PDF exceeds GIF conversion budget")
    return _create_job(
        db, principal, "pdf-to-gif", [req.file_id],
        {"dpi": req.dpi, "frame_ms": req.frame_ms},
    )
