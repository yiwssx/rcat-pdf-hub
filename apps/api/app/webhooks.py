import hashlib
import hmac
import json
import time
from urllib.parse import urlsplit

import httpx
from sqlalchemy.orm import Session

from app.audit import audit_event
from app.config import get_settings
from app.models import JobRecord, ServicePolicy

settings = get_settings()


def _host_allowed(host: str, allowed_hosts: list[str]) -> bool:
    host = host.lower().rstrip(".")
    for item in allowed_hosts:
        rule = item.lower().rstrip(".")
        if rule == "*":
            return True
        if rule.startswith("*.") and (host == rule[2:] or host.endswith(rule[1:])):
            return True
        if host == rule:
            return True
    return False


def validate_webhook_url(url: str) -> str:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Webhook URL must use http or https")
    if parsed.username or parsed.password:
        raise ValueError("Webhook URL must not contain credentials")
    if not settings.webhook_hosts:
        raise ValueError("Webhooks are disabled until PDFHUB_WEBHOOK_ALLOWED_HOSTS is configured")
    if not _host_allowed(parsed.hostname, settings.webhook_hosts):
        raise ValueError(f"Webhook host is not allowed: {parsed.hostname}")
    return url


def derive_webhook_secret(service_name: str) -> str:
    return hmac.new(
        settings.webhook_master_secret.encode("utf-8"),
        service_name.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _job_payload(job: JobRecord) -> bytes:
    payload = {
        "event": f"job.{job.status}",
        "job": {
            "id": job.id,
            "operation": job.operation,
            "status": job.status,
            "progress": job.progress,
            "output_file_id": job.output_file_id,
            "error": job.error,
            "requested_by": job.requested_by,
            "finished_at": job.finished_at.isoformat() if job.finished_at else None,
        },
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")


def dispatch_job_webhook(db: Session, job: JobRecord) -> bool:
    policy = db.get(ServicePolicy, job.requested_by)
    if not policy or not policy.webhook_url:
        return False
    try:
        url = validate_webhook_url(policy.webhook_url)
    except ValueError as exc:
        audit_event("webhook.blocked", job.requested_by, "job", job.id, {"reason": str(exc)})
        return False

    body = _job_payload(job)
    timestamp = str(int(time.time()))
    secret = derive_webhook_secret(job.requested_by)
    signed = timestamp.encode("ascii") + b"." + body
    signature = hmac.new(secret.encode("ascii"), signed, hashlib.sha256).hexdigest()
    headers = {
        "Content-Type": "application/json",
        "X-PDFHub-Event": f"job.{job.status}",
        "X-PDFHub-Timestamp": timestamp,
        "X-PDFHub-Signature": f"sha256={signature}",
    }

    last_error = "unknown"
    for attempt in range(3):
        try:
            response = httpx.post(url, content=body, headers=headers, timeout=float(settings.webhook_timeout_seconds))
            response.raise_for_status()
            audit_event("webhook.delivered", job.requested_by, "job", job.id, {"status_code": response.status_code})
            return True
        except Exception as exc:
            last_error = str(exc)[-1000:]
            if attempt < 2:
                time.sleep(1 + attempt)

    audit_event("webhook.failed", job.requested_by, "job", job.id, {"error": last_error})
    return False
