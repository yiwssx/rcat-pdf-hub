"""M31 default-off authenticated PDF header/footer submission."""
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
from app.services.pdf_header_footer_bounded import (
    MAX_SOURCE_BYTES,
    validate_header_footer_params,
)

settings = get_settings()
router = APIRouter(prefix="/api/v1/pdf", tags=["pdf (staged)"])


class HeaderFooterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    file_id: str = Field(min_length=1, max_length=36)
    header: str = Field(default="", max_length=256)
    footer: str = Field(default="", max_length=256)
    font_size: int = Field(default=12, ge=8, le=24)
    margin: int = Field(default=30, ge=12, le=144)
    header_align: Literal["left", "center", "right"] = "center"
    footer_align: Literal["left", "center", "right"] = "center"

    @model_validator(mode="after")
    def check_templates(self):
        try:
            validate_header_footer_params(self.model_dump(exclude={"file_id"}))
        except ValueError:
            # Do not reflect submitted strings in error messages or logs.
            raise ValueError("Invalid header/footer settings or text template") from None
        return self


@router.post("/header-and-footer", response_model=JobOut, status_code=202)
def header_footer_request(
    req: HeaderFooterRequest,
    principal: Principal = Depends(require_scope("pdf:header-footer")),
    db: Session = Depends(get_db),
) -> JobOut:
    if not settings.header_footer_tools_enabled:
        raise HTTPException(status_code=404, detail="M31 header/footer is disabled")
    record = db.get(FileRecord, req.file_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Source PDF not found")
    if record.source_system != principal.name:
        raise HTTPException(status_code=403, detail="PDF belongs to another owner")
    if _is_expired(record):
        raise HTTPException(status_code=410, detail="Source PDF expired")
    if record.content_type != "application/pdf" or not record.original_name.lower().endswith(".pdf"):
        raise HTTPException(status_code=415, detail="PDF source required")
    if not 24 <= record.size <= MAX_SOURCE_BYTES:
        raise HTTPException(status_code=413, detail="Source PDF exceeds M31 limit")
    return _create_job(
        db, principal, "header-and-footer", [req.file_id],
        req.model_dump(exclude={"file_id"}),
    )
