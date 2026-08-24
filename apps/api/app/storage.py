import hashlib
import re
import shutil
import uuid
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from fastapi import HTTPException, UploadFile

from app.config import get_settings

settings = get_settings()
SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")
S3_PREFIX = "s3:"


def _require_self_hosted_s3_endpoint() -> str:
    endpoint = (settings.s3_endpoint_url or "").strip()
    if not endpoint:
        raise RuntimeError(
            "S3 storage requires an explicit self-hosted PDFHUB_S3_ENDPOINT_URL by zero-cost policy"
        )
    return endpoint


@lru_cache(maxsize=1)
def s3_client():
    endpoint = _require_self_hosted_s3_endpoint()
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        region_name=settings.s3_region,
        aws_access_key_id=settings.s3_access_key or None,
        aws_secret_access_key=settings.s3_secret_key or None,
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": settings.s3_addressing_style},
            retries={"max_attempts": 5, "mode": "standard"},
        ),
    )


def _bucket_exists() -> bool:
    try:
        s3_client().head_bucket(Bucket=settings.s3_bucket)
        return True
    except ClientError:
        return False


def _ensure_bucket() -> None:
    if settings.storage_backend != "s3":
        return
    _require_self_hosted_s3_endpoint()
    if _bucket_exists():
        return
    if not settings.s3_auto_create_bucket:
        raise RuntimeError(f"S3 bucket does not exist: {settings.s3_bucket}")
    s3_client().create_bucket(Bucket=settings.s3_bucket)


def ensure_storage() -> None:
    for subdir in ("originals", "processed", "temporary", "previews", "audit"):
        (settings.data_dir / subdir).mkdir(parents=True, exist_ok=True)
    (settings.data_dir / "temporary" / "materialized").mkdir(parents=True, exist_ok=True)
    _ensure_bucket()


def safe_filename(name: str) -> str:
    name = Path(name or "upload.bin").name
    cleaned = SAFE_NAME.sub("_", name).strip("._")
    return cleaned[:180] or "upload.bin"


async def save_upload(upload: UploadFile) -> tuple[Path, int, str, str]:
    """Stream an upload into a local staging file before AV/quota/storage commit."""
    ensure_storage()
    original = safe_filename(upload.filename or "upload.bin")
    staged = f"{uuid.uuid4()}-{original}"
    target = settings.data_dir / "temporary" / staged
    digest = hashlib.sha256()
    total = 0

    with target.open("wb") as fh:
        while chunk := await upload.read(1024 * 1024):
            total += len(chunk)
            if total > settings.max_upload_bytes:
                target.unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail="File too large")
            digest.update(chunk)
            fh.write(chunk)

    return target, total, digest.hexdigest(), original


def _s3_key(area: str, filename: str) -> str:
    prefix = settings.s3_prefix.strip("/")
    parts = [part for part in (prefix, area.strip("/"), Path(filename).name) if part]
    return "/".join(parts)


def store_staged_file(path: Path, area: str, filename: str | None = None) -> str:
    """Commit a staged local file to local/NAS storage or a self-hosted S3-compatible object store."""
    ensure_storage()
    name = Path(filename or path.name).name
    if settings.storage_backend == "s3":
        key = _s3_key(area, name)
        extra = {}
        if settings.s3_server_side_encryption:
            extra["ServerSideEncryption"] = settings.s3_server_side_encryption
        kwargs = {"ExtraArgs": extra} if extra else {}
        s3_client().upload_file(str(path), settings.s3_bucket, key, **kwargs)
        path.unlink(missing_ok=True)
        return S3_PREFIX + key

    target = settings.data_dir / area / name
    target.parent.mkdir(parents=True, exist_ok=True)
    if path.resolve() != target.resolve():
        try:
            path.replace(target)
        except OSError:
            shutil.copy2(path, target)
            path.unlink(missing_ok=True)
    return target.name


def is_s3_stored_name(stored_name: str) -> bool:
    return stored_name.startswith(S3_PREFIX)


def _materialized_s3_path(key: str) -> Path:
    suffix = Path(key).suffix[:16]
    token = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return settings.data_dir / "temporary" / "materialized" / f"{token}{suffix}"


def path_for_stored_name(stored_name: str) -> Path:
    ensure_storage()
    if is_s3_stored_name(stored_name):
        key = stored_name[len(S3_PREFIX):]
        if not key or key.startswith("/") or ".." in Path(key).parts:
            raise FileNotFoundError(stored_name)
        target = _materialized_s3_path(key)
        if not target.exists():
            try:
                s3_client().download_file(settings.s3_bucket, key, str(target))
            except ClientError as exc:
                target.unlink(missing_ok=True)
                raise FileNotFoundError(stored_name) from exc
        return target

    safe = Path(stored_name).name
    for folder in ("originals", "processed"):
        candidate = settings.data_dir / folder / safe
        if candidate.exists():
            return candidate
    raise FileNotFoundError(stored_name)


def delete_stored_name(stored_name: str) -> int:
    ensure_storage()
    if is_s3_stored_name(stored_name):
        key = stored_name[len(S3_PREFIX):]
        removed = 0
        try:
            head = s3_client().head_object(Bucket=settings.s3_bucket, Key=key)
            removed = int(head.get("ContentLength") or 0)
            s3_client().delete_object(Bucket=settings.s3_bucket, Key=key)
        except ClientError as exc:
            code = str(exc.response.get("Error", {}).get("Code", ""))
            if code not in {"404", "NoSuchKey", "NotFound"}:
                raise
        _materialized_s3_path(key).unlink(missing_ok=True)
        return removed

    safe = Path(stored_name).name
    removed = 0
    for folder in ("originals", "processed"):
        candidate = settings.data_dir / folder / safe
        if candidate.exists():
            removed += candidate.stat().st_size
            candidate.unlink()
    return removed


def new_output_path(job_id: str, suffix: str = ".pdf") -> Path:
    ensure_storage()
    return settings.data_dir / "temporary" / f"output-{job_id}{suffix}"


def preview_path(file_id: str, page: int, width: int) -> Path:
    ensure_storage()
    return settings.data_dir / "previews" / f"{file_id}-p{page}-w{width}.png"


def delete_previews(file_id: str) -> int:
    ensure_storage()
    removed = 0
    for item in (settings.data_dir / "previews").glob(f"{file_id}-*.png"):
        removed += item.stat().st_size
        item.unlink()
    return removed


def default_expiry() -> datetime:
    return datetime.now(timezone.utc) + timedelta(hours=settings.retention_hours)
