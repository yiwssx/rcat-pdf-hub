"""T90-4 M33 opt-in owner-bound AcroForm text filling HTTP intake.

No signature or flattening claims. Routes are absent from default OpenAPI.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import FileRecord
from app.routers.pdf import _create_job, _is_expired
from app.schemas import JobOut
from app.security import Principal, require_scope
from app.services.pdf_acroform_fill import (
    MAX_FIELDS, MAX_FIELD_NAME, MAX_SOURCE_BYTES, MAX_VALUE_LENGTH,
)

router = APIRouter(prefix="/api/v1/pdf/advanced", tags=["advanced-pdf (staged)"])
settings = get_settings()


class PdfFormFillRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    file_id: str = Field(min_length=1, max_length=36)
    updates: dict[str, str] = Field(min_length=1, max_length=MAX_FIELDS)

    @field_validator("updates")
    @classmethod
    def validate_updates(cls, values: dict[str, str]) -> dict[str, str]:
        for name, value in values.items():
            if (not isinstance(name, str) or not 1 <= len(name) <= MAX_FIELD_NAME
                    or any(ord(ch) < 32 or ord(ch) == 127 for ch in name)
                    or not isinstance(value, str) or len(value) > MAX_VALUE_LENGTH
                    or any(ord(ch) < 32 and ch not in "\t\n" for ch in value)):
                raise ValueError("Form field name/value outside supported text bounds")
        return values


@router.post("/fill-pdf-form", response_model=JobOut, status_code=202)
def fill_pdf_form(
    req: PdfFormFillRequest,
    principal: Principal = Depends(require_scope("pdf:convert")),
    db: Session = Depends(get_db),
):
    if not settings.pdf_filler_tools_enabled:
        raise HTTPException(status_code=404, detail="Staged PDF form filler disabled")
    source = db.get(FileRecord, req.file_id)
    if source is None:
        raise HTTPException(status_code=404, detail="File not found")
    if source.source_system != principal.name:
        raise HTTPException(status_code=403, detail="File belongs to another owner")
    if _is_expired(source):
        raise HTTPException(status_code=410, detail="PDF form has expired")
    if source.content_type != "application/pdf" or not source.original_name.lower().endswith(".pdf"):
        raise HTTPException(status_code=415, detail="Only an uploaded PDF form is accepted")
    if not 24 <= source.size <= MAX_SOURCE_BYTES:
        raise HTTPException(status_code=413, detail="PDF form exceeds input size budget")
    return _create_job(
        db, principal, "fill-pdf-form", [req.file_id],
        {"updates": req.updates},
    )
