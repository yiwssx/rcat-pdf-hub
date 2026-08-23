import json
import logging
import os
from collections import deque
from datetime import datetime, timezone
from typing import Any

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


def _audit_path():
    folder = settings.data_dir / "audit"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / "audit.jsonl"


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
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event,
        "actor": actor,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "details": details or {},
    }
    line = (json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    try:
        path = _audit_path()
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
    try:
        path = _audit_path()
        if not path.exists():
            return []
        items: deque[str] = deque(maxlen=limit)
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    items.append(line)
    except OSError as exc:
        logger.error("audit read failed: %s", exc)
        return []

    result: list[dict[str, Any]] = []
    for line in reversed(items):
        try:
            result.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return result
