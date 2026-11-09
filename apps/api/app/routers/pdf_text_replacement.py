"""M01 explicitly gated exact text-object editing, not full PDF/Thai editing."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import FileRecord
from app.routers.pdf import _create_job, _is_expired
from app.schemas import JobOut
from app.security import Principal, require_scope
from app.services.pdf_text_replacement import (
    MAX_PAGES, MAX_SOURCE_BYTES, MAX_TEXT_CHARS, validate_edit,
)

router = APIRouter(prefix="/api/v1/pdf/advanced", tags=["advanced-pdf (staged)"])
settings = get_settings()


class EditExistingTextRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    file_id: str = Field(min_length=1, max_length=36)
    page: StrictInt = Field(ge=1, le=MAX_PAGES)
    old_text: str = Field(min_length=3, max_length=MAX_TEXT_CHARS)
    new_text: str = Field(min_length=3, max_length=MAX_TEXT_CHARS)

    @model_validator(mode="after")
    def check(self):
        validate_edit(page=self.page, old_text=self.old_text, new_text=self.new_text)
        return self


@router.post("/edit-existing-text", response_model=JobOut, status_code=202)
def edit_existing_text(
    req: EditExistingTextRequest,
    principal: Principal = Depends(require_scope("pdf:stamp")),
    db: Session = Depends(get_db),
) -> JobOut:
    if not settings.pdf_edit_text_tools_enabled:
        raise HTTPException(status_code=404, detail="M01 edit text disabled")
    source = db.get(FileRecord, req.file_id)
    if source is None:
        raise HTTPException(status_code=404, detail="PDF not found")
    # A wildcard/admin role never bypasses ownership for this tool.
    if source.source_system != principal.name:
        raise HTTPException(status_code=403, detail="PDF belongs to another owner")
    if _is_expired(source):
        raise HTTPException(status_code=410, detail="PDF expired")
    if source.content_type != "application/pdf" or not source.original_name.lower().endswith(".pdf"):
        raise HTTPException(status_code=415, detail="Verified PDF file required")
    if not 24 <= source.size <= MAX_SOURCE_BYTES:
        raise HTTPException(status_code=413, detail="PDF outside M01 input budget")
    return _create_job(db, principal, "edit-existing-pdf-text", [source.id], {
        "page": req.page, "old_text": req.old_text, "new_text": req.new_text,
    })
