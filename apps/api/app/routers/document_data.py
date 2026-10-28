"""Opt-in-only T90-1.4b API; never mounted by default.

The 90-tool registry is planning-only until T90-5 signoff. No new operations
are added to the reviewed 13-tool legacy route or adapter dictionaries.
"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import FileRecord
from app.routers.pdf import _create_job, _is_expired
from app.schemas import JobOut
from app.security import Principal, require_scope

router = APIRouter(prefix="/api/v1/pdf/document-data", tags=["document-data (staged)"])
settings = get_settings()

MetadataField = Literal["title", "author", "subject", "keywords"]


class EditInfoRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    file_id: str = Field(min_length=1, max_length=36)
    changes: dict[MetadataField, str | None] = Field(min_length=1, max_length=4)

    @field_validator("changes")
    @classmethod
    def check_changes(cls, value: dict[MetadataField, str | None]) -> dict[MetadataField, str | None]:
        for item in value.values():
            if item is not None and (
                len(item) > 512 or any(ord(char) < 32 or ord(char) == 127 for char in item)
            ):
                raise ValueError("Metadata value must be at most 512 printable characters")
        return value


class DocumentDataInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    file_id: str = Field(min_length=1, max_length=36)


def _staged_owner_pdf(
    db: Session, principal: Principal, file_id: str
) -> None:
    if not settings.document_data_tools_enabled:
        raise HTTPException(status_code=404, detail="Staged PDF tool is disabled")
    record = db.get(FileRecord, file_id)
    if record is None:
        raise HTTPException(status_code=404, detail="File not found")
    # T90 staging is stricter than legacy operations: *all* principal types
    # must own the file; worker revalidates ownership before processing.
    if record.source_system != principal.name:
        raise HTTPException(status_code=403, detail="File belongs to another owner")
    if _is_expired(record):
        raise HTTPException(status_code=410, detail="File data has expired")
    if record.content_type != "application/pdf":
        raise HTTPException(status_code=415, detail="Only verified PDF MIME is accepted")


@router.post("/edit-metadata", response_model=JobOut, status_code=202)
def edit_metadata(
    req: EditInfoRequest,
    principal: Principal = Depends(require_scope("pdf:metadata")),
    db: Session = Depends(get_db),
):
    _staged_owner_pdf(db, principal, req.file_id)
    return _create_job(db, principal, "edit-metadata", [req.file_id], {"changes": req.changes})


@router.post("/remove-metadata", response_model=JobOut, status_code=202)
def remove_metadata(
    req: DocumentDataInput,
    principal: Principal = Depends(require_scope("pdf:metadata")),
    db: Session = Depends(get_db),
):
    _staged_owner_pdf(db, principal, req.file_id)
    return _create_job(db, principal, "remove-metadata", [req.file_id], {})


@router.post("/extract-text", response_model=JobOut, status_code=202)
def extract_text(
    req: DocumentDataInput,
    principal: Principal = Depends(require_scope("pdf:extract-text")),
    db: Session = Depends(get_db),
):
    _staged_owner_pdf(db, principal, req.file_id)
    return _create_job(db, principal, "extract-text", [req.file_id], {})
