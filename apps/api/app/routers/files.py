from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import FileRecord
from app.schemas import FileOut
from app.security import Principal, require_scope
from app.storage import default_expiry, path_for_stored_name, save_upload

router = APIRouter(prefix="/api/v1/files", tags=["files"])


@router.post("", response_model=FileOut)
async def upload_file(
    file: UploadFile = File(...),
    principal: Principal = Depends(require_scope("files:write")),
    db: Session = Depends(get_db),
):
    path, size, digest, original = await save_upload(file)
    record = FileRecord(
        original_name=original,
        stored_name=path.name,
        content_type=file.content_type or "application/octet-stream",
        size=size,
        sha256=digest,
        source_system=principal.name,
        expires_at=default_expiry(),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.get("/{file_id}", response_model=FileOut)
def file_info(
    file_id: str,
    _: Principal = Depends(require_scope("files:read")),
    db: Session = Depends(get_db),
):
    record = db.get(FileRecord, file_id)
    if not record:
        raise HTTPException(status_code=404, detail="File not found")
    if "*" not in _.scopes and record.source_system != _.name:
        raise HTTPException(status_code=403, detail="File belongs to another service")
    return record


@router.get("/{file_id}/download")
def download_file(
    file_id: str,
    _: Principal = Depends(require_scope("files:read")),
    db: Session = Depends(get_db),
):
    record = db.get(FileRecord, file_id)
    if not record:
        raise HTTPException(status_code=404, detail="File not found")
    if "*" not in _.scopes and record.source_system != _.name:
        raise HTTPException(status_code=403, detail="File belongs to another service")
    try:
        path = path_for_stored_name(record.stored_name)
    except FileNotFoundError:
        raise HTTPException(status_code=410, detail="File data has expired")
    return FileResponse(path, media_type=record.content_type, filename=record.original_name)
