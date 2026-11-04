"""M16 owner-scoped, default-disabled PDF page extraction API."""
from __future__ import annotations

from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import FileRecord
from app.page_ranges import validated_page_range
from app.routers.pdf import _create_job, _is_expired
from app.schemas import JobOut
from app.security import Principal, require_scope
from app.services.pdf_split_zip import MAX_SOURCE_BYTES

settings = get_settings()
router = APIRouter(prefix="/api/v1/pdf", tags=["pdf (staged)"])


class ExtractPagesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    file_id: str = Field(min_length=1, max_length=36)
    pages: str = Field(min_length=1, max_length=256)
    format: Literal["pdf", "zip"] = "pdf"

    @field_validator("pages")
    @classmethod
    def check_pages(cls, value: str) -> str:
        return validated_page_range(value)


@router.post("/extract-pages", status_code=202, response_model=JobOut)
def extract_pages(
    req: ExtractPagesRequest,
    principal: Principal = Depends(require_scope("pdf:split")),
    db: Session = Depends(get_db),
) -> JobOut:
    if not settings.extract_pages_tools_enabled:
        raise HTTPException(status_code=404, detail="M16 page extraction disabled")
    if req.format == "zip" and not settings.multi_output_artifacts_enabled:
        raise HTTPException(status_code=404, detail="M16 ZIP extraction disabled")
    source = db.get(FileRecord, req.file_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source PDF not found")
    if source.source_system != principal.name:
        raise HTTPException(status_code=403, detail="Source PDF belongs to another owner")
    if _is_expired(source):
        raise HTTPException(status_code=410, detail="Source PDF has expired")
    if (source.content_type != "application/pdf"
            or not source.original_name.lower().endswith(".pdf")):
        raise HTTPException(status_code=415, detail="Verified PDF input required")
    if not 24 <= source.size <= MAX_SOURCE_BYTES:
        raise HTTPException(status_code=413, detail="Source PDF outside M16 byte budget")
    operation = "extract-pages-zip" if req.format == "zip" else "extract-pages-pdf"
    return _create_job(db, principal, operation, [req.file_id], {
        "pages": req.pages, "format": req.format,
    })
