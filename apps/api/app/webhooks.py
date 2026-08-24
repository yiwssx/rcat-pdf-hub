import hashlib
import hmac
import ipaddress
import json
import socket
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import audit_event
from app.config import get_settings
from app.models import JobRecord, ServicePolicy, WebhookDelivery

settings = get_settings()
ACTIVE_DELIVERY_STATUSES = {"queued", "retrying"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _host_allowed(host: str, allowed_hosts: list[str]) -> bool:
    host = host.lower().rstrip(".")
    for item in allowed_hosts:
        rule = item.lower().rstrip(".")
        if rule == "*":
            continue
        if rule.startswith("*.") and host.endswith(rule[1:]) and host != rule[2:]:
            return True
        if host == rule:
            return True
    return False


def _resolved_addresses(host: str, port: int) -> set[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ValueError(f"Webhook host cannot be resolved: {host}") from exc
    addresses: set[ipaddress.IPv4Address | ipaddress.IPv6Address] = set()
    for info in infos:
        raw = info[4][0].split("%", 1)[0]
        addresses.add(ipaddress.ip_address(raw))
    if not addresses:
        raise ValueError(f"Webhook host has no usable addresses: {host}")
    return addresses


def validate_webhook_url(url: str) -> str:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Webhook URL must use http or https")
    if parsed.username or parsed.password:
        raise ValueError("Webhook URL must not contain credentials")
    if parsed.fragment:
        raise ValueError("Webhook URL must not contain a fragment")
    if not settings.webhook_hosts:
        raise ValueError("Webhooks are disabled until PDFHUB_WEBHOOK_ALLOWED_HOSTS is configured")
    if not _host_allowed(parsed.hostname, settings.webhook_hosts):
        raise ValueError(f"Webhook host is not allowed: {parsed.hostname}")

    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    addresses = _resolved_addresses(parsed.hostname, port)
    if not settings.webhook_allow_private_networks:
        blocked = sorted(str(ip) for ip in addresses if not ip.is_global)
        if blocked:
            raise ValueError(f"Webhook host resolves to a non-public address: {', '.join(blocked)}")
    return url


def derive_webhook_secret(service_name: str) -> str:
    return hmac.new(
        settings.webhook_master_secret.encode("utf-8"),
        service_name.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _job_payload(job: JobRecord, delivery: WebhookDelivery) -> bytes:
    payload = {
        "event": delivery.event,
        "delivery": {"id": delivery.id, "attempt": delivery.attempt_count},
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


def queue_job_webhook(db: Session, job: JobRecord) -> WebhookDelivery | None:
    policy = db.get(ServicePolicy, job.requested_by)
    if not policy or not policy.webhook_url:
        return None
    delivery = WebhookDelivery(
        job_id=job.id,
        service_name=job.requested_by,
        url=policy.webhook_url,
        event=f"job.{job.status}",
        status="queued",
        attempt_count=0,
        max_attempts=settings.webhook_max_attempts,
        next_attempt_at=_now(),
    )
    db.add(delivery)
    db.commit()
    db.refresh(delivery)
    audit_event(
        "webhook.queued",
        job.requested_by,
        "webhook_delivery",
        delivery.id,
        {"job_id": job.id, "event": delivery.event, "max_attempts": delivery.max_attempts},
    )
    return delivery


def _retry_delay(attempt_count: int) -> int:
    exponent = max(0, attempt_count - 1)
    return min(
        settings.webhook_retry_initial_seconds * (2 ** exponent),
        settings.webhook_retry_max_seconds,
    )


def deliver_webhook(db: Session, delivery: WebhookDelivery) -> bool:
    if delivery.status not in ACTIVE_DELIVERY_STATUSES:
        return delivery.status == "delivered"
    job = db.get(JobRecord, delivery.job_id)
    if not job:
        delivery.status = "dead"
        delivery.last_error = "Job record no longer exists"
        delivery.updated_at = _now()
        db.commit()
        audit_event(
            "webhook.dead_lettered",
            delivery.service_name,
            "webhook_delivery",
            delivery.id,
            {"error": delivery.last_error},
        )
        return False

    delivery.attempt_count += 1
    delivery.updated_at = _now()
    body = _job_payload(job, delivery)
    timestamp = str(int(time.time()))
    secret = derive_webhook_secret(delivery.service_name)
    signed = timestamp.encode("ascii") + b"." + body
    signature = hmac.new(secret.encode("ascii"), signed, hashlib.sha256).hexdigest()
    headers = {
        "Content-Type": "application/json",
        "X-PDFHub-Event": delivery.event,
        "X-PDFHub-Delivery": delivery.id,
        "X-PDFHub-Attempt": str(delivery.attempt_count),
        "X-PDFHub-Timestamp": timestamp,
        "X-PDFHub-Signature": f"sha256={signature}",
    }

    try:
        url = validate_webhook_url(delivery.url)
        response = httpx.post(
            url,
            content=body,
            headers=headers,
            timeout=float(settings.webhook_timeout_seconds),
            follow_redirects=False,
        )
        delivery.last_status_code = response.status_code
        response.raise_for_status()
    except Exception as exc:
        delivery.last_error = str(exc)[-4000:]
        status_code = getattr(getattr(exc, "response", None), "status_code", None)
        if status_code is not None:
            delivery.last_status_code = int(status_code)
        if delivery.attempt_count >= delivery.max_attempts:
            delivery.status = "dead"
            delivery.next_attempt_at = _now()
            db.commit()
            audit_event(
                "webhook.dead_lettered",
                delivery.service_name,
                "webhook_delivery",
                delivery.id,
                {
                    "job_id": delivery.job_id,
                    "attempts": delivery.attempt_count,
                    "status_code": delivery.last_status_code,
                    "error": delivery.last_error[-1000:],
                },
            )
            return False
        delay = _retry_delay(delivery.attempt_count)
        delivery.status = "retrying"
        delivery.next_attempt_at = _now() + timedelta(seconds=delay)
        db.commit()
        audit_event(
            "webhook.retry_scheduled",
            delivery.service_name,
            "webhook_delivery",
            delivery.id,
            {
                "job_id": delivery.job_id,
                "attempt": delivery.attempt_count,
                "retry_in_seconds": delay,
                "status_code": delivery.last_status_code,
            },
        )
        return False

    delivery.status = "delivered"
    delivery.last_error = None
    delivery.delivered_at = _now()
    delivery.next_attempt_at = delivery.delivered_at
    db.commit()
    audit_event(
        "webhook.delivered",
        delivery.service_name,
        "webhook_delivery",
        delivery.id,
        {
            "job_id": delivery.job_id,
            "attempts": delivery.attempt_count,
            "status_code": delivery.last_status_code,
        },
    )
    return True


def process_due_webhooks(db: Session, limit: int | None = None) -> int:
    batch = limit or settings.webhook_dispatch_batch_size
    now = _now()
    rows = db.scalars(
        select(WebhookDelivery)
        .where(WebhookDelivery.status.in_(ACTIVE_DELIVERY_STATUSES))
        .order_by(WebhookDelivery.next_attempt_at, WebhookDelivery.created_at)
        .limit(batch)
    ).all()
    due = [row for row in rows if _aware(row.next_attempt_at) <= now]
    for delivery in due:
        deliver_webhook(db, delivery)
    return len(due)


def retry_dead_webhook(db: Session, delivery: WebhookDelivery, actor: str) -> WebhookDelivery:
    if delivery.status != "dead":
        raise ValueError("Only dead-letter webhook deliveries can be retried")
    delivery.status = "queued"
    delivery.attempt_count = 0
    delivery.last_error = None
    delivery.last_status_code = None
    delivery.delivered_at = None
    delivery.next_attempt_at = _now()
    delivery.updated_at = _now()
    db.commit()
    db.refresh(delivery)
    audit_event(
        "webhook.requeued",
        actor,
        "webhook_delivery",
        delivery.id,
        {"job_id": delivery.job_id},
    )
    return delivery


def dispatch_job_webhook(db: Session, job: JobRecord) -> bool:
    """Backward-compatible entry point; Phase 4 makes delivery durable and asynchronous."""
    return queue_job_webhook(db, job) is not None
