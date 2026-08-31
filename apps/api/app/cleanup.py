import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select

from app.audit import audit_event, prune_audit_files
from app.config import get_settings
from app.db import SessionLocal
from app.models import ArchiveRecord, FileRecord, JobRecord, WebhookDelivery
from app.storage import delete_previews, delete_stored_name, ensure_storage

settings = get_settings()


def _active_input_ids(db) -> set[str]:
    protected: set[str] = set()
    rows = db.scalars(select(JobRecord).where(JobRecord.status.in_(("queued", "running")))).all()
    for job in rows:
        try:
            values = json.loads(job.input_file_ids_json)
        except (TypeError, json.JSONDecodeError):
            continue
        if isinstance(values, list):
            protected.update(str(value) for value in values)
    return protected


def cleanup_once() -> dict[str, int]:
    ensure_storage()
    db = SessionLocal()
    removed_files = 0
    removed_bytes = 0
    removed_records = 0
    temporary_files = 0
    history_jobs = 0
    history_webhooks = 0
    history_archives = 0
    now = datetime.now(timezone.utc)
    try:
        protected = _active_input_ids(db)
        expired = db.scalars(
            select(FileRecord).where(FileRecord.expires_at.is_not(None), FileRecord.expires_at <= now)
        ).all()
        for record in expired:
            if record.id in protected:
                continue
            removed = delete_stored_name(record.stored_name) + delete_previews(record.id)
            if removed:
                removed_files += 1
                removed_bytes += removed
            db.delete(record)
            removed_records += 1

        job_cutoff = now - timedelta(days=settings.job_history_days)
        result = db.execute(
            delete(JobRecord).where(
                JobRecord.status.in_(("completed", "failed")),
                JobRecord.created_at < job_cutoff,
            )
        )
        history_jobs = int(result.rowcount or 0)

        webhook_cutoff = now - timedelta(days=settings.webhook_history_days)
        result = db.execute(
            delete(WebhookDelivery).where(
                WebhookDelivery.status.in_(("delivered", "dead")),
                WebhookDelivery.updated_at < webhook_cutoff,
            )
        )
        history_webhooks = int(result.rowcount or 0)

        archive_cutoff = now - timedelta(days=settings.archive_history_days)
        result = db.execute(
            delete(ArchiveRecord).where(
                ArchiveRecord.status.in_(("submitted", "failed")),
                ArchiveRecord.updated_at < archive_cutoff,
            )
        )
        history_archives = int(result.rowcount or 0)
        db.commit()

        temp_cutoff = now - timedelta(hours=settings.cleanup_temporary_hours)
        temp_dir = settings.data_dir / "temporary"
        for item in temp_dir.iterdir() if temp_dir.exists() else []:
            try:
                modified = datetime.fromtimestamp(item.stat().st_mtime, tz=timezone.utc)
                if item.is_file() and modified <= temp_cutoff:
                    removed_bytes += item.stat().st_size
                    item.unlink()
                    temporary_files += 1
            except OSError:
                continue

        audit_files_removed = prune_audit_files(settings.audit_retention_days)
        result = {
            "expired_records_scanned": len(expired),
            "expired_records_purged": removed_records,
            "files_removed": removed_files,
            "temporary_files_removed": temporary_files,
            "bytes_removed": removed_bytes,
            "history_jobs_removed": history_jobs,
            "history_webhooks_removed": history_webhooks,
            "history_archives_removed": history_archives,
            "audit_files_removed": audit_files_removed,
        }
        audit_event("retention.cleanup", "cleanup-worker", "storage", None, result)
        return result
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
