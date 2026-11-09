"""M25/M26/M29 authenticated source-preserving PDF markup submissions."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import FileRecord
from app.routers.pdf import _create_job, _is_expired
from app.schemas import JobOut
from app.security import Principal, require_scope
from app.services.pdf_markup import MAX_PAGES, MAX_SOURCE_BYTES, MAX_TEXT, validate_markup

router = APIRouter(prefix="/api/v1/pdf/advanced", tags=["advanced-pdf (staged)"])
settings = get_settings()


class PdfMarkupRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    file_id: str = Field(min_length=1, max_length=36)
    mode: Literal["annotation", "highlight", "whiteout"]
    page: StrictInt = Field(ge=1, le=MAX_PAGES)
    x: float = Field(ge=0, le=4000, allow_inf_nan=False)
    y: float = Field(ge=0, le=4000, allow_inf_nan=False)
    width: float = Field(ge=8, le=1500, allow_inf_nan=False)
    height: float = Field(ge=8, le=1500, allow_inf_nan=False)
    text: str = Field(default="", max_length=MAX_TEXT)

    @model_validator(mode="after")
    def check(self):
        validate_markup(
            mode=self.mode, page=self.page, x=self.x, y=self.y,
            width=self.width, height=self.height, text=self.text,
        )
        return self


@router.post("/markup", status_code=202, response_model=JobOut)
def submit_pdf_markup(
    req: PdfMarkupRequest,
    principal: Principal = Depends(require_scope("pdf:stamp")),
    db: Session = Depends(get_db),
) -> JobOut:
    if not settings.pdf_markup_tools_enabled:
        raise HTTPException(status_code=404, detail="M25/M26/M29 PDF markup disabled")
    source = db.get(FileRecord, req.file_id)
    if source is None:
        raise HTTPException(status_code=404, detail="PDF not found")
    if source.source_system != principal.name:
        raise HTTPException(status_code=403, detail="PDF belongs to another owner")
    if _is_expired(source):
        raise HTTPException(status_code=410, detail="PDF expired")
    if (source.content_type != "application/pdf"
            or not source.original_name.lower().endswith(".pdf")):
        raise HTTPException(status_code=415, detail="Verified PDF required")
    if not 24 <= source.size <= MAX_SOURCE_BYTES:
        raise HTTPException(status_code=413, detail="PDF exceeds bounded markup source budget")
    return _create_job(
        db, principal, "pdf-markup", [req.file_id],
        req.model_dump(exclude={"file_id"}),
    )
