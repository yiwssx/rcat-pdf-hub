from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import desc, or_, select
from sqlalchemy.orm import Session

from app.audit import audit_event
from app.config import get_settings
from app.db import get_db
from app.malware import MalwareDetected, scan_file
from app.models import FileRecord
from app.policy import ensure_storage_quota
from app.schemas import FileOut
from app.security import Principal, require_scope
from app.services import pdf_tools
from app.storage import (
    default_expiry,
    delete_stored_name,
    path_for_stored_name,
    preview_path,
    save_upload,
    store_staged_file,
)

router = APIRouter(prefix="/api/v1/files", tags=["files"])
settings = get_settings()


def _aware(value):
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _owned_file(db: Session, file_id: str, principal: Principal) -> FileRecord:
    record = db.get(FileRecord, file_id)
    if not record:
        raise HTTPException(status_code=404, detail="File not found")
    if "*" not in principal.scopes and record.source_system != principal.name:
        raise HTTPException(status_code=403, detail="File belongs to another service")
    return record


@router.get("", response_model=list[FileOut])
def list_files(
    limit: int = Query(default=50, ge=1, le=200),
    include_expired: bool = Query(default=False),
    principal: Principal = Depends(require_scope("files:read")),
    db: Session = Depends(get_db),
):
    stmt = select(FileRecord).order_by(desc(FileRecord.created_at)).limit(limit)
    if not include_expired:
        now = datetime.now(timezone.utc)
        stmt = stmt.where(or_(FileRecord.expires_at.is_(None), FileRecord.expires_at > now))
    if "*" not in principal.scopes:
        stmt = stmt.where(FileRecord.source_system == principal.name)
    return db.scalars(stmt).all()


@router.post("", response_model=FileOut)
async def upload_file(
    file: UploadFile = File(...),
    principal: Principal = Depends(require_scope("files:write")),
    db: Session = Depends(get_db),
):
    staged, size, digest, original = await save_upload(file)
    stored_name: str | None = None
    try:
        try:
            scan_status = scan_file(staged)
        except MalwareDetected as exc:
            audit_event(
                "file.malware_rejected",
                principal.name,
                "file",
                None,
                {"name": original, "size": size, "signature": str(exc)[:500]},
            )
            raise HTTPException(status_code=422, detail="Uploaded file was rejected by malware scanning") from exc
        audit_event("file.malware_scanned", principal.name, "file", None, {"name": original, "status": scan_status})

        if not principal.is_bootstrap_admin:
            ensure_storage_quota(db, principal.name, principal.max_storage_mb, size)

        stored_name = store_staged_file(staged, "originals")
        record = FileRecord(
            original_name=original,
            stored_name=stored_name,
            content_type=file.content_type or "application/octet-stream",
            size=size,
            sha256=digest,
            source_system=principal.name,
            expires_at=default_expiry(),
        )
        db.add(record)
        db.commit()
        db.refresh(record)
    except HTTPException:
        db.rollback()
        staged.unlink(missing_ok=True)
        if stored_name:
            delete_stored_name(stored_name)
        raise
    except Exception:
        db.rollback()
        staged.unlink(missing_ok=True)
        if stored_name:
            delete_stored_name(stored_name)
        raise

    audit_event(
        "file.uploaded",
        principal.name,
        "file",
        record.id,
        {"name": original, "size": size, "sha256": digest, "storage_backend": settings.storage_backend},
    )
    return record


@router.get("/{file_id}", response_model=FileOut)
def file_info(
    file_id: str,
    principal: Principal = Depends(require_scope("files:read")),
    db: Session = Depends(get_db),
):
    return _owned_file(db, file_id, principal)


@router.get("/{file_id}/download")
def download_file(
    file_id: str,
    principal: Principal = Depends(require_scope("files:read")),
    db: Session = Depends(get_db),
):
    record = _owned_file(db, file_id, principal)
    expires_at = _aware(record.expires_at)
    if expires_at and expires_at <= datetime.now(timezone.utc):
        raise HTTPException(status_code=410, detail="File data has expired")
    try:
        path = path_for_stored_name(record.stored_name)
    except FileNotFoundError:
        raise HTTPException(status_code=410, detail="File data has expired")
    audit_event("file.downloaded", principal.name, "file", record.id, {"name": record.original_name})
    return FileResponse(path, media_type=record.content_type, filename=record.original_name)


@router.get("/{file_id}/preview")
def preview_file(
    file_id: str,
    page: int = Query(default=1, ge=1, le=5000),
    width: int = Query(default=720, ge=160),
    principal: Principal = Depends(require_scope("files:read")),
    db: Session = Depends(get_db),
):
    record = _owned_file(db, file_id, principal)
    expires_at = _aware(record.expires_at)
    if expires_at and expires_at <= datetime.now(timezone.utc):
        raise HTTPException(status_code=410, detail="File data has expired")
    if record.content_type != "application/pdf" and not record.original_name.lower().endswith(".pdf"):
        raise HTTPException(status_code=415, detail="Preview is available for PDF files only")
    width = min(width, settings.preview_max_width)
    try:
        source = path_for_stored_name(record.stored_name)
    except FileNotFoundError:
        raise HTTPException(status_code=410, detail="File data has expired")
    target = preview_path(record.id, page, width)
    if not target.exists():
        try:
            pdf_tools.render_preview(source, target, page=page, width=width)
        except RuntimeError as exc:
            raise HTTPException(status_code=422, detail=str(exc)[-1000:]) from exc
    audit_event("file.previewed", principal.name, "file", record.id, {"page": page, "width": width})
    return FileResponse(target, media_type="image/png", filename=f"{record.id}-p{page}.png")
