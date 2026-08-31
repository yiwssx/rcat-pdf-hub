from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import FileRecord, JobRecord, ServicePolicy

settings = get_settings()


@dataclass(frozen=True)
class EffectivePolicy:
    service_name: str
    rate_limit_per_minute: int
    daily_job_limit: int
    max_storage_mb: int
    webhook_url: str | None = None


def effective_policy(db: Session, service_name: str) -> EffectivePolicy:
    row = db.get(ServicePolicy, service_name)
    if row:
        return EffectivePolicy(
            service_name=service_name,
            rate_limit_per_minute=row.rate_limit_per_minute,
            daily_job_limit=row.daily_job_limit,
            max_storage_mb=row.max_storage_mb,
            webhook_url=row.webhook_url,
        )
    return EffectivePolicy(
        service_name=service_name,
        rate_limit_per_minute=settings.default_rate_limit_per_minute,
        daily_job_limit=settings.default_daily_job_limit,
        max_storage_mb=settings.default_max_storage_mb,
        webhook_url=None,
    )


def _lock_principal_quota(db: Session, service_name: str) -> None:
    """Serialize quota check+commit for a principal within the current transaction."""
    bind = db.get_bind()
    if bind.dialect.name == "postgresql":
        db.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:service_name))"),
            {"service_name": service_name},
        )
        return
    db.execute(
        select(ServicePolicy.service_name)
        .where(ServicePolicy.service_name == service_name)
        .with_for_update()
    )


def ensure_rate_limit(service_name: str, per_minute: int) -> None:
    if per_minute <= 0:
        return
    try:
        from app.queue import redis_conn

        bucket = datetime.now(timezone.utc).strftime("%Y%m%d%H%M")
        key = f"pdfhub:rate:{service_name}:{bucket}"
        count = redis_conn.incr(key)
        if count == 1:
            redis_conn.expire(key, 120)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Rate-limit backend unavailable",
            headers={"Retry-After": "5"},
        ) from exc

    if count > per_minute:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Service rate limit exceeded",
            headers={"Retry-After": "60"},
        )


def ensure_daily_job_quota(db: Session, service_name: str, daily_limit: int) -> None:
    if daily_limit <= 0:
        return
    _lock_principal_quota(db, service_name)
    now = datetime.now(timezone.utc)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    count = db.scalar(
        select(func.count())
        .select_from(JobRecord)
        .where(JobRecord.requested_by == service_name, JobRecord.created_at >= start)
    ) or 0
    if count >= daily_limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Daily job quota exceeded ({daily_limit})",
        )


def active_storage_bytes(db: Session, service_name: str) -> int:
    now = datetime.now(timezone.utc)
    total = db.scalar(
        select(func.coalesce(func.sum(FileRecord.size), 0)).where(
            FileRecord.source_system == service_name,
            or_(FileRecord.expires_at.is_(None), FileRecord.expires_at > now),
        )
    )
    return int(total or 0)


def ensure_storage_quota(db: Session, service_name: str, max_storage_mb: int, incoming_bytes: int) -> None:
    if max_storage_mb <= 0:
        return
    _lock_principal_quota(db, service_name)
    limit = max_storage_mb * 1024 * 1024
    if active_storage_bytes(db, service_name) + incoming_bytes > limit:
        raise HTTPException(
            status_code=413,
            detail=f"Service storage quota exceeded ({max_storage_mb} MB)",
        )
