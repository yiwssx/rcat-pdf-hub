import hashlib
import re
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from app.config import get_settings

settings = get_settings()
SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


def ensure_storage() -> None:
    for subdir in ("originals", "processed", "temporary"):
        (settings.data_dir / subdir).mkdir(parents=True, exist_ok=True)


def safe_filename(name: str) -> str:
    name = Path(name or "upload.bin").name
    cleaned = SAFE_NAME.sub("_", name).strip("._")
    return cleaned[:180] or "upload.bin"


async def save_upload(upload: UploadFile) -> tuple[Path, int, str, str]:
    ensure_storage()
    original = safe_filename(upload.filename or "upload.bin")
    stored = f"{uuid.uuid4()}-{original}"
    target = settings.data_dir / "originals" / stored
    digest = hashlib.sha256()
    total = 0

    with target.open("wb") as fh:
        while chunk := await upload.read(1024 * 1024):
            total += len(chunk)
            if total > settings.max_upload_bytes:
                fh.close()
                target.unlink(missing_ok=True)
                raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="File too large")
            digest.update(chunk)
            fh.write(chunk)

    return target, total, digest.hexdigest(), original


def path_for_stored_name(stored_name: str) -> Path:
    for folder in ("originals", "processed"):
        candidate = settings.data_dir / folder / Path(stored_name).name
        if candidate.exists():
            return candidate
    raise FileNotFoundError(stored_name)


def new_output_path(job_id: str, suffix: str = ".pdf") -> Path:
    ensure_storage()
    return settings.data_dir / "processed" / f"{job_id}{suffix}"


def default_expiry() -> datetime:
    return datetime.now(timezone.utc) + timedelta(hours=settings.retention_hours)
