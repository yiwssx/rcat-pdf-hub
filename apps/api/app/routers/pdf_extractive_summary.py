"""M03 offline extractive summary; owner-scoped, strictly default OFF."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, StrictInt
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import FileRecord
from app.routers.pdf import _create_job, _is_expired
from app.schemas import JobOut
from app.security import Principal, require_scope
from app.services.pdf_extractive_summary import MAX_SOURCE_BYTES, MAX_SENTENCES

router = APIRouter(prefix="/api/v1/pdf/advanced", tags=["advanced-pdf (staged)"])
settings = get_settings()


class ExtractiveSummaryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    file_id: str = Field(min_length=1, max_length=36)
    sentence_count: StrictInt = Field(default=6, ge=1, le=MAX_SENTENCES)


@router.post("/extractive-summary", status_code=202, response_model=JobOut)
def summarize_pdf(
    req: ExtractiveSummaryRequest,
    principal: Principal = Depends(require_scope("pdf:extract-text")),
    db: Session = Depends(get_db),
) -> JobOut:
    if not settings.pdf_extractive_summary_tools_enabled:
        raise HTTPException(status_code=404, detail="M03 summary disabled")
    source = db.get(FileRecord, req.file_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source PDF not found")
    if source.source_system != principal.name:
        raise HTTPException(status_code=403, detail="Source PDF belongs to another owner")
    if _is_expired(source):
        raise HTTPException(status_code=410, detail="PDF has expired")
    if (source.content_type != "application/pdf"
            or not source.original_name.lower().endswith(".pdf")):
        raise HTTPException(status_code=415, detail="Verified PDF required")
    if not 24 <= source.size <= MAX_SOURCE_BYTES:
        raise HTTPException(status_code=413, detail="M03 PDF size outside budget")
    return _create_job(
        db, principal, "pdf-extractive-summary", [req.file_id],
        {"sentence_count": req.sentence_count},
    )
