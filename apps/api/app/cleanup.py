from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.audit import audit_event
from app.config import get_settings
from app.db import SessionLocal
from app.models import FileRecord
from app.storage import delete_previews, delete_stored_name, ensure_storage

settings = get_settings()


def cleanup_once() -> dict[str, int]:
    ensure_storage()
    db = SessionLocal()
    removed_files = 0
    removed_bytes = 0
    temporary_files = 0
    now = datetime.now(timezone.utc)
    try:
        expired = db.scalars(select(FileRecord).where(FileRecord.expires_at.is_not(None), FileRecord.expires_at <= now)).all()
        for record in expired:
            removed = delete_stored_name(record.stored_name) + delete_previews(record.id)
            if removed:
                removed_files += 1
                removed_bytes += removed

        temp_cutoff = now - timedelta(hours=settings.cleanup_temporary_hours)
        temp_dir = settings.data_dir / "temporary"
        for item in temp_dir.iterdir() if temp_dir.exists() else []:
            try:
                modified = datetime.fromtimestamp(item.stat().st_mtime, tz=timezone.utc)
                if item.is_file() and modified <= temp_cutoff:
                    removed_bytes += item.stat().st_size
                    item.unlink(missing_ok=True)
                    temporary_files += 1
            except OSError:
                continue

        result = {
            "expired_records_scanned": len(expired),
            "files_removed": removed_files,
            "temporary_files_removed": temporary_files,
            "bytes_removed": removed_bytes,
        }
        audit_event("retention.cleanup", "cleanup-worker", "storage", None, result)
        return result
    finally:
        db.close()


if __name__ == "__main__":
    print(cleanup_once())
