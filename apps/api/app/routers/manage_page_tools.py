"""Default-disabled owner-scoped M14 delete and M15 reorder PDF pages."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, StrictInt
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import FileRecord
from app.routers.pdf import _create_job, _is_expired
from app.schemas import JobOut
from app.security import Principal, require_scope
from app.services.pdf_page_selection import MAX_SOURCE_BYTES

router = APIRouter(prefix="/api/v1/pdf/manage-pages", tags=["pdf"])
settings = get_settings()


class DeletePagesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    file_id: str = Field(min_length=1, max_length=36)
    pages: list[StrictInt] = Field(min_length=1, max_length=120)


class ReorderPagesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    file_id: str = Field(min_length=1, max_length=36)
    order: list[StrictInt] = Field(min_length=1, max_length=120)


def _submit(file_id: str, principal: Principal, db: Session,
            operation: str, pages: list[int]) -> JobOut:
    if not settings.manage_page_tools_enabled:
        raise HTTPException(status_code=404, detail="T90-4 page tools are disabled")
    source = db.get(FileRecord, file_id)
    if source is None:
        raise HTTPException(status_code=404, detail="PDF not found")
    if source.source_system != principal.name:
        raise HTTPException(status_code=403, detail="PDF belongs to another owner")
    if _is_expired(source):
        raise HTTPException(status_code=410, detail="PDF has expired")
    if (source.content_type != "application/pdf"
            or not source.original_name.lower().endswith(".pdf")):
        raise HTTPException(status_code=415, detail="Verified PDF required")
    if not 24 <= source.size <= MAX_SOURCE_BYTES:
        raise HTTPException(status_code=413, detail="Source PDF exceeds page budget")
    return _create_job(db, principal, operation, [file_id], {"pages": pages})


@router.post("/delete", status_code=202, response_model=JobOut)
def delete_pages(
    request: DeletePagesRequest,
    principal: Principal = Depends(require_scope("pdf:split")),
    db: Session = Depends(get_db),
):
    return _submit(request.file_id, principal, db, "delete-pdf-pages", request.pages)


@router.post("/reorder", status_code=202, response_model=JobOut)
def reorder_pages(
    request: ReorderPagesRequest,
    principal: Principal = Depends(require_scope("pdf:split")),
    db: Session = Depends(get_db),
):
    return _submit(request.file_id, principal, db, "reorder-pdf-pages", request.order)
