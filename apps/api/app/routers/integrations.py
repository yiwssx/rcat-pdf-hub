from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.audit import audit_event
from app.config import get_settings
from app.db import get_db
from app.integrations.paperless import archive_to_paperless
from app.models import ArchiveRecord, FileRecord
from app.schemas import ArchiveOut
from app.security import Principal, get_principal, require_scope
from app.storage import path_for_stored_name

router = APIRouter(prefix="/api/v1/integrations", tags=["integrations"])
settings = get_settings()


def _owned_file(db: Session, file_id: str, principal: Principal) -> FileRecord:
    record = db.get(FileRecord, file_id)
    if not record:
        raise HTTPException(status_code=404, detail="File not found")
    if "*" not in principal.scopes and record.source_system != principal.name:
        raise HTTPException(status_code=403, detail="File belongs to another service")
    return record


@router.get("/status")
def integration_status(_: Principal = Depends(get_principal)):
    return {
        "storage_backend": settings.storage_backend,
        "clamav_enabled": settings.clamav_enabled,
        "paperless_enabled": settings.paperless_enabled,
        "oidc_enabled": settings.oidc_enabled,
        "ldap_enabled": settings.ldap_enabled,
        "otel_enabled": bool(settings.otel_endpoint),
        "prometheus_enabled": settings.prometheus_enabled,
    }


@router.get("/paperless/archives", response_model=list[ArchiveOut])
def list_paperless_archives(
    limit: int = Query(default=100, ge=1, le=500),
    principal: Principal = Depends(require_scope("archive:paperless")),
    db: Session = Depends(get_db),
):
    stmt = select(ArchiveRecord).where(ArchiveRecord.integration_name == "paperless").order_by(desc(ArchiveRecord.created_at)).limit(limit)
    rows = db.scalars(stmt).all()
    if "*" in principal.scopes:
        return rows
    owned_ids = set(db.scalars(select(FileRecord.id).where(FileRecord.source_system == principal.name)).all())
    return [row for row in rows if row.file_id in owned_ids]


@router.post("/paperless/{file_id}", response_model=ArchiveOut)
def archive_file_to_paperless(
    file_id: str,
    principal: Principal = Depends(require_scope("archive:paperless")),
    db: Session = Depends(get_db),
):
    if not settings.paperless_enabled:
        raise HTTPException(status_code=404, detail="Paperless integration is disabled")
    record = _owned_file(db, file_id, principal)
    archive = db.scalar(
        select(ArchiveRecord).where(
            ArchiveRecord.file_id == record.id,
            ArchiveRecord.integration_name == "paperless",
        )
    )
    if not archive:
        archive = ArchiveRecord(file_id=record.id, integration_name="paperless", status="submitting")
        db.add(archive)
    else:
        archive.status = "submitting"
        archive.error = None
    db.commit()
    db.refresh(archive)

    try:
        path = path_for_stored_name(record.stored_name)
        archive.external_id = archive_to_paperless(record, path)
        archive.status = "submitted"
        archive.error = None
        db.commit()
        db.refresh(archive)
    except Exception as exc:
        db.rollback()
        archive = db.get(ArchiveRecord, archive.id)
        if archive:
            archive.status = "failed"
            archive.error = str(exc)[-4000:]
            db.commit()
            db.refresh(archive)
        audit_event("archive.paperless_failed", principal.name, "file", record.id, {"error": str(exc)[-1000:]})
        raise HTTPException(status_code=502, detail="Paperless archive submission failed") from exc

    audit_event(
        "archive.paperless_submitted",
        principal.name,
        "file",
        record.id,
        {"task_id": archive.external_id},
    )
    return archive
