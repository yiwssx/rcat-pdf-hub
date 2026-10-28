"""T90-1.5 opt-in HTTP intake. Disabled routes are absent from OpenAPI."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import FileRecord
from app.routers.pdf import _create_job, _is_expired
from app.schemas import JobOut
from app.security import Principal, require_scope

router = APIRouter(prefix="/api/v1/pdf/geometry", tags=["geometry (staged)"])
settings = get_settings()


class _PdfInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    file_id: str = Field(min_length=1, max_length=36)


class CropRequest(_PdfInput):
    left: float = Field(ge=-14400, le=14400, allow_inf_nan=False)
    bottom: float = Field(ge=-14400, le=14400, allow_inf_nan=False)
    right: float = Field(ge=-14400, le=14400, allow_inf_nan=False)
    top: float = Field(ge=-14400, le=14400, allow_inf_nan=False)
    pages: list[int] | None = Field(default=None, min_length=1, max_length=1000)

    @model_validator(mode="after")
    def validate_geometry(self):
        if not 10 <= self.right - self.left <= 14400:
            raise ValueError("Crop width outside 10–14400 PDF points")
        if not 10 <= self.top - self.bottom <= 14400:
            raise ValueError("Crop height outside 10–14400 PDF points")
        if self.pages is not None and (
            any(type(page) is not int or page < 1 or page > 1000 for page in self.pages)
            or len(self.pages) != len(set(self.pages))
        ):
            raise ValueError("Pages must be unique 1-based integers (maximum 1000)")
        return self


class ResizeRequest(_PdfInput):
    width: float = Field(ge=10, le=14400, allow_inf_nan=False)
    height: float = Field(ge=10, le=14400, allow_inf_nan=False)


def _require_owned_pdf(db: Session, principal: Principal, file_id: str) -> None:
    if not settings.geometry_tools_enabled:
        raise HTTPException(status_code=404, detail="Staged geometry tools are disabled")
    record = db.get(FileRecord, file_id)
    if record is None:
        raise HTTPException(status_code=404, detail="File not found")
    if record.source_system != principal.name:
        raise HTTPException(status_code=403, detail="File belongs to another owner")
    if _is_expired(record):
        raise HTTPException(status_code=410, detail="File data has expired")
    if record.content_type != "application/pdf":
        raise HTTPException(status_code=415, detail="Only verified PDF MIME is accepted")


@router.post("/crop-pdf", response_model=JobOut, status_code=202)
def crop_pdf_job(
    req: CropRequest,
    principal: Principal = Depends(require_scope("pdf:crop")),
    db: Session = Depends(get_db),
):
    _require_owned_pdf(db, principal, req.file_id)
    return _create_job(db, principal, "crop-pdf", [req.file_id],
                       req.model_dump(exclude={"file_id"}))


@router.post("/resize-pdf", response_model=JobOut, status_code=202)
def resize_pdf_job(
    req: ResizeRequest,
    principal: Principal = Depends(require_scope("pdf:resize")),
    db: Session = Depends(get_db),
):
    _require_owned_pdf(db, principal, req.file_id)
    return _create_job(db, principal, "resize-pdf", [req.file_id],
                       req.model_dump(exclude={"file_id"}))
