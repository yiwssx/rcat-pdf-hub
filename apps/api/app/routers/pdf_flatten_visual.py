"""M24: owner-scoped static visual-flatten PDF staging API."""
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
from app.services.pdf_flatten_visual import MAX_SOURCE_BYTES

router = APIRouter(prefix="/api/v1/pdf/advanced", tags=["advanced-pdf (staged)"])
settings = get_settings()


class FlattenPdfRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    file_id: str = Field(min_length=1, max_length=36)


@router.post("/flatten-visual", status_code=202, response_model=JobOut)
def flatten_pdf_visual(
    req: FlattenPdfRequest,
    principal: Principal = Depends(require_scope("pdf:convert")),
    db: Session = Depends(get_db),
) -> JobOut:
    if not settings.pdf_flatten_visual_tools_enabled:
        raise HTTPException(status_code=404, detail="M24 visual flatten disabled")
    source = db.get(FileRecord, req.file_id)
    if source is None:
        raise HTTPException(status_code=404, detail="PDF not found")
    if source.source_system != principal.name:
        raise HTTPException(status_code=403, detail="PDF belongs to a different owner")
    if _is_expired(source):
        raise HTTPException(status_code=410, detail="PDF expired")
    if (source.content_type != "application/pdf"
            or not source.original_name.lower().endswith(".pdf")):
        raise HTTPException(status_code=415, detail="Verified PDF required")
    if not 24 <= source.size <= MAX_SOURCE_BYTES:
        raise HTTPException(status_code=413, detail="M24 source size exceeds budget")
    return _create_job(db, principal, "flatten-pdf-visual", [req.file_id], {})
