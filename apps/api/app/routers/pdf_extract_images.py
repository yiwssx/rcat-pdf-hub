"""M18 authenticated ZIP extraction of genuine PDF embedded images."""
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
from app.services.pdf_extract_embedded_images import MAX_SOURCE_BYTES

settings = get_settings()
router = APIRouter(prefix="/api/v1/pdf", tags=["pdf (staged)"])


class ExtractImagesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    file_id: str = Field(min_length=1, max_length=36)


@router.post("/extract-images", response_model=JobOut, status_code=202)
def extract_images(
    req: ExtractImagesRequest,
    principal: Principal = Depends(require_scope("pdf:extract-images")),
    db: Session = Depends(get_db),
) -> JobOut:
    if not settings.extract_embedded_images_tools_enabled:
        raise HTTPException(status_code=404, detail="M18 image extraction disabled")
    record = db.get(FileRecord, req.file_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Source PDF not found")
    if record.source_system != principal.name:
        raise HTTPException(status_code=403, detail="PDF belongs to another owner")
    if _is_expired(record):
        raise HTTPException(status_code=410, detail="Source PDF expired")
    if record.content_type != "application/pdf" or not record.original_name.lower().endswith(".pdf"):
        raise HTTPException(status_code=415, detail="Verified PDF source required")
    if not 24 <= record.size <= MAX_SOURCE_BYTES:
        raise HTTPException(status_code=413, detail="PDF exceeds M18 source size budget")
    return _create_job(db, principal, "extract-images", [req.file_id], {})
