import json
import logging
import os
from collections import deque
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


def _audit_folder() -> Path:
    folder = settings.data_dir / "audit"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _audit_path(now: datetime | None = None) -> Path:
    stamp = (now or datetime.now(timezone.utc)).strftime("%Y-%m-%d")
    return _audit_folder() / f"audit-{stamp}.jsonl"


def _audit_paths() -> list[Path]:
    folder = _audit_folder()
    paths = sorted(folder.glob("audit-????-??-??.jsonl"), reverse=True)
    legacy = folder / "audit.jsonl"
    if legacy.exists():
        paths.append(legacy)
    return paths


def _write_all(fd: int, data: bytes) -> None:
    offset = 0
    while offset < len(data):
        written = os.write(fd, data[offset:])
        if written <= 0:
            raise OSError("audit write returned zero bytes")
        offset += written


def audit_event(
    event: str,
    actor: str,
    resource_type: str | None = None,
    resource_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> bool:
    now = datetime.now(timezone.utc)
    payload = {
        "timestamp": now.isoformat(),
        "event": event,
        "actor": actor,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "details": details or {},
    }
    line = (json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    try:
        path = _audit_path(now)
        fd = os.open(path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
        try:
            _write_all(fd, line)
        finally:
            os.close(fd)
        return True
    except OSError as exc:
        logger.error("audit persistence failed: %s", exc)
        return False


def read_audit_events(limit: int = 200) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    try:
        for path in _audit_paths():
            items: deque[str] = deque(maxlen=limit)
            with path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    if line.strip():
                        items.append(line)
            for line in reversed(items):
                try:
                    result.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
                if len(result) >= limit:
                    return result
    except OSError as exc:
        logger.error("audit read failed: %s", exc)
    return result


def prune_audit_files(retention_days: int | None = None) -> int:
    days = retention_days or settings.audit_retention_days
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    removed = 0
    current = _audit_path()
    for path in _audit_paths():
        if path == current:
            continue
        try:
            modified = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
            if modified < cutoff:
                path.unlink()
                removed += 1
        except OSError:
            logger.exception("audit prune failed for %s", path)
    return removed
