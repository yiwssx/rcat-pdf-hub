"""M05 gated owner-scoped PDF text translation."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import FileRecord
from app.routers.pdf import _create_job, _is_expired
from app.schemas import JobOut
from app.security import Principal, require_scope
from app.services.pdf_private_translation import MAX_SOURCE_BYTES, validate_languages

router = APIRouter(prefix="/api/v1/pdf/translation", tags=["pdf-translation (staged)"])
settings = get_settings()


class TranslatePdfRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    file_id: str = Field(min_length=1, max_length=36)
    source_language: Literal["en", "th"]
    target_language: Literal["en", "th"]

    @model_validator(mode="after")
    def check_language_pair(self):
        validate_languages(self.source_language, self.target_language)
        return self


def _submit(req: TranslatePdfRequest, principal: Principal,
            db: Session, operation: str) -> JobOut:
    if not settings.pdf_translation_tools_enabled:
        raise HTTPException(status_code=404, detail="M05 translation disabled")
    pdf = db.get(FileRecord, req.file_id)
    if pdf is None:
        raise HTTPException(status_code=404, detail="PDF not found")
    if pdf.source_system != principal.name:
        raise HTTPException(status_code=403, detail="PDF belongs to another owner")
    if _is_expired(pdf):
        raise HTTPException(status_code=410, detail="PDF expired")
    if pdf.content_type != "application/pdf" or not pdf.original_name.lower().endswith(".pdf"):
        raise HTTPException(status_code=415, detail="Verified PDF required")
    if not 24 <= pdf.size <= MAX_SOURCE_BYTES:
        raise HTTPException(status_code=413, detail="PDF outside M05 source budget")
    return _create_job(db, principal, operation, [pdf.id], {
        "source_language": req.source_language,
        "target_language": req.target_language,
    })


@router.post("/text", response_model=JobOut, status_code=202)
def translate_text(
    req: TranslatePdfRequest,
    principal: Principal = Depends(require_scope("pdf:extract-text")),
    db: Session = Depends(get_db),
) -> JobOut:
    return _submit(req, principal, db, "translate-pdf-text")


@router.post("/pdf", response_model=JobOut, status_code=202)
def translate_document(
    req: TranslatePdfRequest,
    principal: Principal = Depends(require_scope("pdf:extract-text")),
    db: Session = Depends(get_db),
) -> JobOut:
    return _submit(req, principal, db, "translate-pdf-document")
