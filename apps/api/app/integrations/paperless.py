from pathlib import Path

import httpx

from app.config import get_settings
from app.models import FileRecord

settings = get_settings()


def _headers() -> dict[str, str]:
    return {"Authorization": f"Token {settings.paperless_token}"}


def paperless_health() -> bool:
    if not settings.paperless_enabled:
        return True
    try:
        response = httpx.get(
            settings.paperless_url.rstrip("/") + "/api/",
            headers=_headers(),
            timeout=settings.paperless_timeout_seconds,
            follow_redirects=False,
        )
        return response.status_code < 500
    except httpx.HTTPError:
        return False


def archive_to_paperless(record: FileRecord, path: Path) -> str:
    if not settings.paperless_enabled:
        raise RuntimeError("Paperless integration is disabled")
    url = settings.paperless_url.rstrip("/") + "/api/documents/post_document/"
    with path.open("rb") as fh:
        response = httpx.post(
            url,
            headers=_headers(),
            files={"document": (record.original_name, fh, record.content_type)},
            data={"title": record.original_name},
            timeout=settings.paperless_timeout_seconds,
            follow_redirects=False,
        )
    response.raise_for_status()
    try:
        payload = response.json()
    except ValueError:
        payload = response.text.strip()
    if isinstance(payload, dict):
        task_id = payload.get("task_id") or payload.get("id") or payload.get("uuid")
    else:
        task_id = payload
    task_id = str(task_id or "").strip('"')
    if not task_id:
        raise RuntimeError("Paperless accepted the document but returned no task id")
    return task_id
