import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import desc, or_, select, update
from sqlalchemy.orm import Session

from app.audit import audit_event
from app.config import get_settings
from app.db import get_db
from app.downloads import issue_signed_download, verify_signed_download
from app.malware import MalwareDetected, scan_file
from app.filetypes import validate_uploaded_file
from app.models import ArchiveRecord, FileRecord, JobRecord
from app.policy import ensure_storage_quota
from app.schemas import FileBulkDeleteRequest, FileOut, FileRetentionUpdate, PageInfoOut, SignedDownloadOut
from app.security import Principal, require_scope
from app.services import pdf_tools
from pypdf import PdfReader
from app.storage import (
    default_expiry,
    delete_previews,
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


def _active_file_path(record: FileRecord):
    expires_at = _aware(record.expires_at)
    if expires_at and expires_at <= datetime.now(timezone.utc):
        raise HTTPException(status_code=410, detail="File data has expired")
    try:
        return path_for_stored_name(record.stored_name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=410, detail="File data has expired") from exc


def _active_job_uses_file(db: Session, file_id: str) -> bool:
    rows = db.scalars(select(JobRecord).where(JobRecord.status.in_(("queued", "running")))).all()
    for job in rows:
        try:
            if file_id in json.loads(job.input_file_ids_json):
                return True
        except (TypeError, json.JSONDecodeError):
            continue
    return False


def _delete_file_record(db: Session, record: FileRecord, principal: Principal) -> int:
    if _active_job_uses_file(db, record.id):
        raise HTTPException(status_code=409, detail="File is being used by an active job")
    removed_bytes = delete_stored_name(record.stored_name) + delete_previews(record.id)
    db.execute(update(JobRecord).where(JobRecord.output_file_id == record.id).values(output_file_id=None))
    for archive in db.scalars(select(ArchiveRecord).where(ArchiveRecord.file_id == record.id)).all():
        db.delete(archive)
    db.delete(record)
    db.commit()
    audit_event("file.deleted", principal.name, "file", record.id, {"name": record.original_name, "bytes_removed": removed_bytes})
    return removed_bytes


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
        normalized_content_type = validate_uploaded_file(staged, original)

        if not principal.is_bootstrap_admin:
            ensure_storage_quota(db, principal.name, principal.max_storage_mb, size)

        stored_name = store_staged_file(staged, "originals")
        record = FileRecord(
            original_name=original,
            stored_name=stored_name,
            content_type=normalized_content_type,
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
    path = _active_file_path(record)
    audit_event("file.downloaded", principal.name, "file", record.id, {"name": record.original_name})
    return FileResponse(path, media_type=record.content_type, filename=record.original_name)


@router.post("/{file_id}/signed-download", response_model=SignedDownloadOut)
def create_signed_download(
    file_id: str,
    ttl_seconds: int | None = Query(default=None, ge=30),
    principal: Principal = Depends(require_scope("files:read")),
    db: Session = Depends(get_db),
):
    record = _owned_file(db, file_id, principal)
    _active_file_path(record)
    try:
        signed = issue_signed_download(record.id, record.source_system, ttl_seconds)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    url = (
        settings.public_base_url.rstrip("/")
        + f"/api/v1/files/{record.id}/signed-download?expires={signed.expires}&token={signed.token}"
    )
    expires_at = datetime.fromtimestamp(signed.expires, tz=timezone.utc)
    audit_event(
        "file.signed_download_issued",
        principal.name,
        "file",
        record.id,
        {"expires_at": expires_at.isoformat()},
    )
    return SignedDownloadOut(file_id=record.id, url=url, expires_at=expires_at)


@router.get("/{file_id}/signed-download")
def signed_download_file(
    file_id: str,
    expires: int = Query(..., ge=1),
    token: str = Query(..., min_length=64, max_length=64),
    db: Session = Depends(get_db),
):
    record = db.get(FileRecord, file_id)
    if not record:
        raise HTTPException(status_code=404, detail="File not found")
    if not verify_signed_download(record.id, record.source_system, expires, token):
        raise HTTPException(status_code=403, detail="Signed download URL is invalid or expired")
    path = _active_file_path(record)
    audit_event(
        "file.signed_downloaded",
        record.source_system,
        "file",
        record.id,
        {"expires": expires},
    )
    return FileResponse(path, media_type=record.content_type, filename=record.original_name)


@router.get("/{file_id}/pages", response_model=PageInfoOut)
def page_info(
    file_id: str,
    principal: Principal = Depends(require_scope("files:read")),
    db: Session = Depends(get_db),
):
    record = _owned_file(db, file_id, principal)
    if record.content_type != "application/pdf" and not record.original_name.lower().endswith(".pdf"):
        raise HTTPException(status_code=415, detail="Page information is available for PDF files only")
    try:
        pages = len(PdfReader(str(_active_file_path(record))).pages)
    except Exception as exc:
        raise HTTPException(status_code=422, detail="Unable to read PDF page count") from exc
    return PageInfoOut(file_id=record.id, pages=pages)


@router.post("/{file_id}/retention", response_model=FileOut)
def update_retention(
    file_id: str,
    req: FileRetentionUpdate,
    principal: Principal = Depends(require_scope("files:write")),
    db: Session = Depends(get_db),
):
    record = _owned_file(db, file_id, principal)
    record.expires_at = None if req.keep else default_expiry()
    db.commit()
    db.refresh(record)
    audit_event("file.retention_updated", principal.name, "file", record.id, {"keep": req.keep})
    return record


@router.delete("/{file_id}")
def delete_file(
    file_id: str,
    principal: Principal = Depends(require_scope("files:write")),
    db: Session = Depends(get_db),
):
    record = _owned_file(db, file_id, principal)
    removed = _delete_file_record(db, record, principal)
    return {"deleted": [file_id], "bytes_removed": removed}


@router.post("/bulk-delete")
def bulk_delete_files(
    req: FileBulkDeleteRequest,
    principal: Principal = Depends(require_scope("files:write")),
    db: Session = Depends(get_db),
):
    records = [_owned_file(db, file_id, principal) for file_id in dict.fromkeys(req.file_ids)]
    for record in records:
        if _active_job_uses_file(db, record.id):
            raise HTTPException(status_code=409, detail=f"File is being used by an active job: {record.id}")
    removed_bytes = 0
    deleted = []
    for record in records:
        removed_bytes += delete_stored_name(record.stored_name) + delete_previews(record.id)
        db.execute(update(JobRecord).where(JobRecord.output_file_id == record.id).values(output_file_id=None))
        for archive in db.scalars(select(ArchiveRecord).where(ArchiveRecord.file_id == record.id)).all():
            db.delete(archive)
        deleted.append(record.id)
        db.delete(record)
    db.commit()
    audit_event("file.bulk_deleted", principal.name, "file", None, {"file_ids": deleted, "bytes_removed": removed_bytes})
    return {"deleted": deleted, "bytes_removed": removed_bytes}


@router.get("/{file_id}/preview")
def preview_file(
    file_id: str,
    page: int = Query(default=1, ge=1, le=5000),
    width: int = Query(default=720, ge=160),
    principal: Principal = Depends(require_scope("files:read")),
    db: Session = Depends(get_db),
):
    record = _owned_file(db, file_id, principal)
    if record.content_type != "application/pdf" and not record.original_name.lower().endswith(".pdf"):
        raise HTTPException(status_code=415, detail="Preview is available for PDF files only")
    width = min(width, settings.preview_max_width)
    source = _active_file_path(record)
    target = preview_path(record.id, page, width)
    if not target.exists():
        try:
            pdf_tools.render_preview(source, target, page=page, width=width)
        except RuntimeError as exc:
            raise HTTPException(status_code=422, detail=str(exc)[-1000:]) from exc
    audit_event("file.previewed", principal.name, "file", record.id, {"page": page, "width": width})
    return FileResponse(target, media_type="image/png", filename=f"{record.id}-p{page}.png")
