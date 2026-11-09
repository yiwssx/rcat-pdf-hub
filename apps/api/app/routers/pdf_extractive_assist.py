"""M03/M06 default-off, owner-scoped extractive PDF analysis routes."""
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
from app.services.pdf_extractive_assist import MAX_SOURCE_BYTES

router = APIRouter(prefix="/api/v1/pdf/document-assist", tags=["pdf-assist (staged)"])
settings = get_settings()


class AssistRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    file_id: str = Field(min_length=1, max_length=36)
    question: str = Field(default="", max_length=250)

    @model_validator(mode="after")
    def check(self):
        if any(ord(c) < 32 for c in self.question):
            raise ValueError("Question contains control characters")
        return self


def _submit(req: AssistRequest, principal: Principal, db: Session,
            mode: Literal["summary", "evidence"]) -> JobOut:
    if not settings.pdf_extractive_assist_tools_enabled:
        raise HTTPException(status_code=404, detail="Document assist disabled")
    if mode == "summary" and req.question:
        raise HTTPException(status_code=422, detail="Summary does not accept question")
    if mode == "evidence" and not 3 <= len(req.question.strip()) <= 250:
        raise HTTPException(status_code=422, detail="Question length outside 3–250")
    record = db.get(FileRecord, req.file_id)
    if record is None:
        raise HTTPException(status_code=404, detail="PDF not found")
    if record.source_system != principal.name:
        raise HTTPException(status_code=403, detail="PDF belongs to another owner")
    if _is_expired(record):
        raise HTTPException(status_code=410, detail="PDF expired")
    if record.content_type != "application/pdf" or not record.original_name.lower().endswith(".pdf"):
        raise HTTPException(status_code=415, detail="Verified PDF file required")
    if not 24 <= record.size <= MAX_SOURCE_BYTES:
        raise HTTPException(status_code=413, detail="PDF over assistant input budget")
    return _create_job(db, principal, "pdf-extractive-" + mode,
                       [record.id], {"question": req.question} if mode == "evidence" else {})


@router.post("/summary", response_model=JobOut, status_code=202)
def summary(req: AssistRequest,
            principal: Principal = Depends(require_scope("pdf:extract-text")),
            db: Session = Depends(get_db)):
    return _submit(req, principal, db, "summary")


@router.post("/evidence", response_model=JobOut, status_code=202)
def evidence(req: AssistRequest,
             principal: Principal = Depends(require_scope("pdf:extract-text")),
             db: Session = Depends(get_db)):
    return _submit(req, principal, db, "evidence")
