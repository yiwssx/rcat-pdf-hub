import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.audit import audit_event
from app.config import get_settings
from app.db import SessionLocal
from app.models import FileRecord, JobRecord
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

        result = {
            "expired_records_scanned": len(expired),
            "expired_records_purged": removed_records,
            "files_removed": removed_files,
            "temporary_files_removed": temporary_files,
            "bytes_removed": removed_bytes,
        }
        audit_event("retention.cleanup", "cleanup-worker", "storage", None, result)
        return result
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
