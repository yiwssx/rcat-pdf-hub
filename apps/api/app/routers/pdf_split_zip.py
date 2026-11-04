"""M07: owner-bound, default-disabled multi-PDF ZIP split route."""
from __future__ import annotations

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

router = APIRouter(prefix="/api/v1/pdf", tags=["pdf (staged)"])
settings = get_settings()


class SplitZipRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    file_id: str = Field(min_length=1, max_length=36)
    pages: str = Field(min_length=1, max_length=256)

    @field_validator("pages")
    @classmethod
    def check_range(cls, value: str) -> str:
        return validated_page_range(value)


@router.post("/split-to-zip", status_code=202, response_model=JobOut)
def split_to_zip(
    req: SplitZipRequest,
    principal: Principal = Depends(require_scope("pdf:split")),
    db: Session = Depends(get_db),
) -> JobOut:
    if not (settings.split_zip_tools_enabled
            and settings.multi_output_artifacts_enabled):
        raise HTTPException(status_code=404, detail="M07 multi-PDF split disabled")
    source = db.get(FileRecord, req.file_id)
    if source is None:
        raise HTTPException(status_code=404, detail="PDF not found")
    # No privileged wildcard bypass for staged tool ownership.
    if source.source_system != principal.name:
        raise HTTPException(status_code=403, detail="PDF belongs to another owner")
    if _is_expired(source):
        raise HTTPException(status_code=410, detail="Source PDF expired")
    if (source.content_type != "application/pdf"
            or not source.original_name.lower().endswith(".pdf")):
        raise HTTPException(status_code=415, detail="Verified PDF required")
    if not 24 <= source.size <= MAX_SOURCE_BYTES:
        raise HTTPException(status_code=413, detail="PDF exceeds M07 split budget")
    return _create_job(db, principal, "split-to-zip", [req.file_id],
                       {"pages": req.pages})
