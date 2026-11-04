"""M22 staged owner-scoped PDF text overlay API, disabled by default.

The endpoint is not a general PDF editor. Only printable ASCII text at one
explicit position on an unrotated unsigned, non-annotated PDF is supported.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import FileRecord
from app.routers.pdf import _create_job, _is_expired
from app.schemas import JobOut
from app.security import Principal, require_scope
from app.services.pdf_text_overlay import (
    MAX_PAGES, MAX_SOURCE_BYTES, MAX_TEXT_CHARS, validate_overlay_parameters,
)

router = APIRouter(prefix="/api/v1/pdf/advanced", tags=["advanced-pdf (staged)"])
settings = get_settings()


class AddPdfTextRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    file_id: str = Field(min_length=1, max_length=36)
    page: StrictInt = Field(ge=1, le=MAX_PAGES)
    x: float = Field(ge=0, le=4000, allow_inf_nan=False)
    y: float = Field(ge=0, le=4000, allow_inf_nan=False)
    font_size: StrictInt = Field(default=12, ge=8, le=24)
    text: str = Field(min_length=1, max_length=MAX_TEXT_CHARS)

    @field_validator("text")
    @classmethod
    def supported_text(cls, text: str) -> str:
        if not text.strip() or any(not 32 <= ord(ch) <= 126 for ch in text):
            raise ValueError("M22 accepts printable ASCII only")
        return text


@router.post("/add-text", status_code=202, response_model=JobOut)
def add_pdf_text(
    req: AddPdfTextRequest,
    principal: Principal = Depends(require_scope("pdf:stamp")),
    db: Session = Depends(get_db),
) -> JobOut:
    if not settings.pdf_text_overlay_tools_enabled:
        raise HTTPException(status_code=404, detail="Staged M22 text overlay disabled")
    source = db.get(FileRecord, req.file_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source PDF not found")
    if source.source_system != principal.name:
        raise HTTPException(status_code=403, detail="PDF belongs to another owner")
    if _is_expired(source):
        raise HTTPException(status_code=410, detail="Source PDF has expired")
    if source.content_type != "application/pdf" or not source.original_name.lower().endswith(".pdf"):
        raise HTTPException(status_code=415, detail="Verified PDF required")
    if not 24 <= source.size <= MAX_SOURCE_BYTES:
        raise HTTPException(status_code=413, detail="PDF exceeds M22 source budget")
    validate_overlay_parameters(
        page=req.page, x=req.x, y=req.y, font_size=req.font_size, text=req.text,
    )
    return _create_job(db, principal, "add-pdf-text", [req.file_id], {
        "page": req.page, "x": req.x, "y": req.y,
        "font_size": req.font_size, "text": req.text,
    })
