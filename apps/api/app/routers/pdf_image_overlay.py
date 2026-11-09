"""M23 opt-in owner-scoped static JPEG/PNG image-on-PDF endpoint."""
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
from app.services.pdf_image_overlay import (
    MAX_IMAGE_BYTES, MAX_PDF_BYTES, MAX_PAGES, validate_image_overlay,
)

router = APIRouter(prefix="/api/v1/pdf/advanced", tags=["advanced-pdf (staged)"])
settings = get_settings()


class AddPdfImageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    file_id: str = Field(min_length=1, max_length=36)
    image_file_id: str = Field(min_length=1, max_length=36)
    page: StrictInt = Field(ge=1, le=MAX_PAGES)
    x: float = Field(ge=0, le=4000, allow_inf_nan=False)
    y: float = Field(ge=0, le=4000, allow_inf_nan=False)
    width: float = Field(ge=8, le=2000, allow_inf_nan=False)
    height: float = Field(ge=8, le=2000, allow_inf_nan=False)

    @model_validator(mode="after")
    def validate_position(self):
        if self.file_id == self.image_file_id:
            raise ValueError("PDF and image must be separate source files")
        validate_image_overlay(
            page=self.page, x=self.x, y=self.y,
            width=self.width, height=self.height,
        )
        return self


@router.post("/add-image", status_code=202, response_model=JobOut)
def add_pdf_image(
    req: AddPdfImageRequest,
    principal: Principal = Depends(require_scope("pdf:stamp")),
    db: Session = Depends(get_db),
) -> JobOut:
    if not settings.pdf_image_overlay_tools_enabled:
        raise HTTPException(status_code=404, detail="M23 staged image overlay disabled")
    pdf = db.get(FileRecord, req.file_id)
    image = db.get(FileRecord, req.image_file_id)
    if pdf is None or image is None:
        raise HTTPException(status_code=404, detail="Required PDF or image file not found")
    if pdf.source_system != principal.name or image.source_system != principal.name:
        raise HTTPException(status_code=403, detail="Input belongs to a different owner")
    if _is_expired(pdf) or _is_expired(image):
        raise HTTPException(status_code=410, detail="Source file has expired")
    if (pdf.content_type != "application/pdf"
            or not pdf.original_name.lower().endswith(".pdf")
            or not 24 <= pdf.size <= MAX_PDF_BYTES):
        raise HTTPException(status_code=415, detail="Unsupported PDF input")
    supported_images = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
    }
    suffix = "." + image.original_name.rsplit(".", 1)[-1].lower()
    if (supported_images.get(suffix) != image.content_type
            or not 16 <= image.size <= MAX_IMAGE_BYTES):
        raise HTTPException(status_code=415, detail="Only bounded JPEG/PNG images are supported")
    return _create_job(db, principal, "add-pdf-image", [pdf.id, image.id], {
        "page": req.page,
        "x": req.x,
        "y": req.y,
        "width": req.width,
        "height": req.height,
    })
