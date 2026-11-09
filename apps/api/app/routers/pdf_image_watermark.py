"""M21 independent image-watermark API, preserving the existing text-watermark route."""
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
from app.services.pdf_image_watermark import (
    MAX_IMAGE_BYTES, MAX_PDF_BYTES, validate_image_watermark,
)

router = APIRouter(prefix="/api/v1/pdf/advanced", tags=["advanced-pdf (staged)"])
settings = get_settings()


class PdfImageWatermarkRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    file_id: str = Field(min_length=1, max_length=36)
    image_file_id: str = Field(min_length=1, max_length=36)
    relative_width: float = Field(default=0.30, ge=0.10, le=0.80, allow_inf_nan=False)
    opacity: float = Field(default=0.20, ge=0.05, le=0.70, allow_inf_nan=False)

    @model_validator(mode="after")
    def checked(self):
        if self.file_id == self.image_file_id:
            raise ValueError("Watermark image and PDF must be distinct")
        validate_image_watermark(
            relative_width=self.relative_width, opacity=self.opacity,
        )
        return self


@router.post("/image-watermark", status_code=202, response_model=JobOut)
def image_watermark(
    req: PdfImageWatermarkRequest,
    principal: Principal = Depends(require_scope("pdf:watermark")),
    db: Session = Depends(get_db),
) -> JobOut:
    if not settings.pdf_image_watermark_tools_enabled:
        raise HTTPException(status_code=404, detail="M21 image watermark disabled")
    pdf = db.get(FileRecord, req.file_id)
    image = db.get(FileRecord, req.image_file_id)
    if pdf is None or image is None:
        raise HTTPException(status_code=404, detail="Source PDF or image missing")
    if pdf.source_system != principal.name or image.source_system != principal.name:
        raise HTTPException(status_code=403, detail="Cross-owner watermark inputs denied")
    if _is_expired(pdf) or _is_expired(image):
        raise HTTPException(status_code=410, detail="Watermark source expired")
    if (pdf.content_type != "application/pdf"
            or not pdf.original_name.lower().endswith(".pdf")
            or not 24 <= pdf.size <= MAX_PDF_BYTES):
        raise HTTPException(status_code=415, detail="Unsupported PDF source")
    allowed = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}
    extension = "." + image.original_name.rsplit(".", 1)[-1].lower()
    if (allowed.get(extension) != image.content_type
            or not 16 <= image.size <= MAX_IMAGE_BYTES):
        raise HTTPException(status_code=415, detail="Only bounded still JPEG/PNG accepted")
    return _create_job(db, principal, "watermark-pdf-image", [pdf.id, image.id], {
        "relative_width": req.relative_width, "opacity": req.opacity,
    })
