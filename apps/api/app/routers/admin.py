import shutil
import json
from typing import Literal

import httpx

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, func, select, text
from sqlalchemy.orm import Session

from app.audit import audit_event, read_audit_events
from app.config import get_settings
from app.db import get_db
from app.models import ApiKey, FileRecord, JobRecord, ServicePolicy, WebhookDelivery
from app.observability import collect_queue_runtime_snapshot
from app.policy import effective_policy
from app.queue import redis_conn
from app.schemas import (
    AdminJobTriageItemOut,
    AdminJobTriagePageOut,
    ApiKeyCreate,
    ApiKeyCreated,
    ApiKeyOut,
    ServicePolicyOut,
    ServicePolicyUpdate,
    StorageReconciliationOut,
    WebhookDeliveryOut,
)
from app.security import Principal, hash_api_key, new_api_key, require_scope
from app.storage_reconciliation import reconcile_storage
from app.webhooks import derive_webhook_secret, retry_dead_webhook, validate_webhook_url

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])
settings = get_settings()

ALLOWED_SCOPES = {
    "files:read", "files:write", "jobs:read", "jobs:manage",
    "pdf:merge", "pdf:split", "pdf:rotate", "pdf:compress",
    "pdf:ocr", "pdf:pdfa", "pdf:convert", "pdf:watermark",
    "pdf:page-number", "pdf:stamp", "pdf:image-to-pdf", "pdf:pdf-to-image",
    "archive:paperless", "admin:keys",
}


def _policy_out(db: Session, service_name: str) -> ServicePolicyOut:
    policy = effective_policy(db, service_name)
    return ServicePolicyOut(
        service_name=service_name,
        rate_limit_per_minute=policy.rate_limit_per_minute,
        daily_job_limit=policy.daily_job_limit,
        max_storage_mb=policy.max_storage_mb,
        webhook_url=policy.webhook_url,
    )


def _out(db: Session, record: ApiKey) -> ApiKeyOut:
    return ApiKeyOut(
        id=record.id,
        name=record.name,
        scopes=json.loads(record.scopes_json),
        active=record.active,
        policy=_policy_out(db, record.name),
    )


def _validated_webhook(url: str | None) -> str | None:
    if not url:
        return None
    try:
        return validate_webhook_url(url)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _require_admin_action_audit(event: str, principal: Principal, kind: str, reference: str | None, details: dict) -> None:
    # Record intent before mutating configuration or scheduling a delivery.
    # A successful response must never hide that audit persistence was down.
    if not audit_event(event, principal.name, kind, reference, details):
        raise HTTPException(status_code=503, detail="Admin action audit unavailable")


def _require_bootstrap_admin(principal: Principal) -> None:
    if not principal.is_bootstrap_admin:
        raise HTTPException(status_code=403, detail="Bootstrap admin required")


@router.get("/status")
def admin_status(
    principal: Principal = Depends(require_scope("admin:keys")),
    db: Session = Depends(get_db),
):
    database_ok = True
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        database_ok = False

    redis_ok = True
    try:
        redis_ok = bool(redis_conn.ping())
    except Exception:
        redis_ok = False

    storage_write_ok = False
    try:
        probe = settings.data_dir / "temporary" / ".diagnostic-write"
        probe.parent.mkdir(parents=True, exist_ok=True)
        probe.write_bytes(b"ok")
        probe.unlink(missing_ok=True)
        storage_write_ok = True
    except OSError:
        storage_write_ok = False

    gotenberg_ok = False
    try:
        response = httpx.get(settings.gotenberg_url.rstrip("/") + "/health", timeout=2.0)
        gotenberg_ok = response.status_code < 500
    except httpx.HTTPError:
        gotenberg_ok = False

    try:
        disk = shutil.disk_usage(settings.data_dir)
        disk_data = {"total": disk.total, "used": disk.used, "free": disk.free}
    except OSError:
        disk_data = {"total": 0, "used": 0, "free": 0}

    queue_depths: dict[str, int] = {}
    worker_pools: dict[str, dict] = {}
    try:
        worker_pools = collect_queue_runtime_snapshot()
        queue_depths = {
            queue_name: int(values["depth"])
            for queue_name, values in worker_pools.items()
        }
        queue_depth = sum(queue_depths.values())
        workers = sum(int(values["workers"]) for values in worker_pools.values())
    except Exception:
        worker_pools = {}
        queue_depths = {}
        queue_depth = -1
        workers = 0

    job_counts = {
        status: int(db.scalar(select(func.count()).select_from(JobRecord).where(JobRecord.status == status)) or 0)
        for status in ("queued", "running", "completed", "failed", "cancelled")
    }
    total_files = int(db.scalar(select(func.count()).select_from(FileRecord)) or 0)
    pdfhub_bytes = int(db.scalar(select(func.coalesce(func.sum(FileRecord.size), 0))) or 0)
    tools = {name: bool(shutil.which(name)) for name in ("qpdf", "gs", "ocrmypdf", "tesseract", "pdftoppm")}

    return {
        "database_ok": database_ok,
        "redis_ok": redis_ok,
        "workers": workers,
        "queue_depth": queue_depth,
        "queue_depths": queue_depths,
        "worker_pools": worker_pools,
        "storage_backend": settings.storage_backend,
        "storage_write_ok": storage_write_ok,
        "gotenberg_ok": gotenberg_ok,
        "data_dir": str(settings.data_dir),
        "disk": disk_data,
        "pdfhub_bytes": pdfhub_bytes,
        "files": total_files,
        "jobs": job_counts,
        "retention_hours": settings.retention_hours,
        "cleanup_temporary_hours": settings.cleanup_temporary_hours,
        "clamav_enabled": settings.clamav_enabled,
        "paperless_enabled": settings.paperless_enabled,
        "tools": tools,
        "auth": {
            "local_admin": settings.local_admin_enabled,
            "oidc": settings.oidc_enabled,
            "ldap": settings.ldap_enabled,
            "web_console_auto_login": settings.web_console_auto_login_enabled,
        },
        "principal": principal.name,
    }


def _require_human_triage_admin(principal: Principal) -> None:
    # Both bootstrap and wildcard service/API-key principals must be denied.
    if (
        not principal.is_identity_admin
        or "admin" not in principal.roles
        or principal.auth_source not in {"oidc", "ldap", "local-admin"}
    ):
        raise HTTPException(status_code=403, detail="Human Admin identity required")


@router.get("/jobs/triage", response_model=AdminJobTriagePageOut)
def list_admin_job_triage(
    status: Literal["queued", "running", "completed", "failed", "cancelled"] | None = Query(default=None),
    operation: str | None = Query(default=None, min_length=1, max_length=40, pattern=r"^[a-z0-9-]+$"),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=100000),
    principal: Principal = Depends(require_scope("admin:keys")),
    db: Session = Depends(get_db),
) -> AdminJobTriagePageOut:
    _require_human_triage_admin(principal)
    # Fail closed if the privileged read cannot be audited.
    if not audit_event(
        "admin.jobs_triage.read", principal.name, "job_triage", None,
        {"status": status, "operation": operation, "limit": limit, "offset": offset},
    ):
        raise HTTPException(status_code=503, detail="Admin audit unavailable")

    stmt = select(
        JobRecord.id, JobRecord.operation, JobRecord.status, JobRecord.progress,
        JobRecord.created_at, JobRecord.started_at, JobRecord.finished_at,
        JobRecord.error.is_not(None).label("failure_recorded"),
    )
    if status is not None:
        stmt = stmt.where(JobRecord.status == status)
    if operation is not None:
        stmt = stmt.where(JobRecord.operation == operation)
    stmt = stmt.order_by(desc(JobRecord.created_at), desc(JobRecord.id))
    rows = db.execute(stmt.offset(offset).limit(limit + 1)).all()
    items = [
        AdminJobTriageItemOut(**dict(row._mapping))
        for row in rows[:limit]
    ]
    return AdminJobTriagePageOut(
        items=items, limit=limit, offset=offset, has_more=len(rows) > limit,
    )


@router.get("/storage-reconciliation", response_model=StorageReconciliationOut)
def storage_reconciliation(
    detail_limit: int = Query(default=200, ge=1, le=2000),
    _: Principal = Depends(require_scope("admin:keys")),
    db: Session = Depends(get_db),
):
    return reconcile_storage(db, detail_limit=detail_limit)


@router.get("/api-keys", response_model=list[ApiKeyOut])
def list_api_keys(
    _: Principal = Depends(require_scope("admin:keys")),
    db: Session = Depends(get_db),
):
    return [_out(db, record) for record in db.scalars(select(ApiKey).order_by(ApiKey.name)).all()]


@router.post("/api-keys", response_model=ApiKeyCreated)
def create_api_key(
    req: ApiKeyCreate,
    principal: Principal = Depends(require_scope("admin:keys")),
    db: Session = Depends(get_db),
):
    invalid = sorted(set(req.scopes) - ALLOWED_SCOPES)
    if invalid:
        raise HTTPException(status_code=422, detail={"invalid_scopes": invalid})
    if "admin:keys" in req.scopes:
        _require_bootstrap_admin(principal)
    if db.scalar(select(ApiKey).where(ApiKey.name == req.name)):
        raise HTTPException(status_code=409, detail="API key name already exists")

    webhook_url = _validated_webhook(req.webhook_url)
    _require_admin_action_audit(
        "api_key.create_requested", principal, "api_key", None,
        {"service": req.name, "scope_count": len(set(req.scopes)), "webhook_configured": bool(webhook_url)},
    )
    secret = new_api_key()
    record = ApiKey(name=req.name, key_hash=hash_api_key(secret), scopes_json=json.dumps(sorted(set(req.scopes))))
    policy = ServicePolicy(
        service_name=req.name,
        rate_limit_per_minute=req.rate_limit_per_minute if req.rate_limit_per_minute is not None else settings.default_rate_limit_per_minute,
        daily_job_limit=req.daily_job_limit if req.daily_job_limit is not None else settings.default_daily_job_limit,
        max_storage_mb=req.max_storage_mb if req.max_storage_mb is not None else settings.default_max_storage_mb,
        webhook_url=webhook_url,
    )
    try:
        db.add(record)
        db.add(policy)
        db.commit()
        db.refresh(record)
    except Exception:
        db.rollback()
        raise
    audit_event("api_key.created", principal.name, "api_key", record.id, {"service": record.name, "scopes": sorted(set(req.scopes))})
    policy_out = _policy_out(db, record.name)
    return ApiKeyCreated(
        id=record.id,
        name=record.name,
        api_key=secret,
        scopes=sorted(set(req.scopes)),
        policy=policy_out,
        webhook_secret=derive_webhook_secret(record.name) if webhook_url else None,
    )


@router.delete("/api-keys/{key_id}", response_model=ApiKeyOut)
def revoke_api_key(
    key_id: str,
    principal: Principal = Depends(require_scope("admin:keys")),
    db: Session = Depends(get_db),
):
    record = db.get(ApiKey, key_id)
    if not record:
        raise HTTPException(status_code=404, detail="API key not found")
    _require_admin_action_audit(
        "api_key.revoke_requested", principal, "api_key", record.id, {"service": record.name},
    )
    record.active = False
    db.commit()
    db.refresh(record)
    audit_event("api_key.revoked", principal.name, "api_key", record.id, {"service": record.name})
    return _out(db, record)


@router.get("/service-policies", response_model=list[ServicePolicyOut])
def list_service_policies(
    _: Principal = Depends(require_scope("admin:keys")),
    db: Session = Depends(get_db),
):
    names = db.scalars(select(ApiKey.name).order_by(ApiKey.name)).all()
    return [_policy_out(db, name) for name in names]


@router.put("/service-policies/{service_name}", response_model=ServicePolicyOut)
def update_service_policy(
    service_name: str,
    req: ServicePolicyUpdate,
    principal: Principal = Depends(require_scope("admin:keys")),
    db: Session = Depends(get_db),
):
    if not db.scalar(select(ApiKey).where(ApiKey.name == service_name)):
        raise HTTPException(status_code=404, detail="Service API key not found")
    webhook_url = _validated_webhook(req.webhook_url)
    _require_admin_action_audit(
        "service_policy.update_requested", principal, "service_policy", service_name,
        {"rate_limit_per_minute": req.rate_limit_per_minute,
         "daily_job_limit": req.daily_job_limit, "max_storage_mb": req.max_storage_mb,
         "webhook_configured": bool(webhook_url)},
    )
    row = db.get(ServicePolicy, service_name)
    if not row:
        row = ServicePolicy(service_name=service_name)
        db.add(row)
    row.rate_limit_per_minute = req.rate_limit_per_minute
    row.daily_job_limit = req.daily_job_limit
    row.max_storage_mb = req.max_storage_mb
    row.webhook_url = webhook_url
    db.commit()
    audit_event(
        "service_policy.updated", principal.name, "service_policy", service_name,
        {
            "rate_limit_per_minute": req.rate_limit_per_minute,
            "daily_job_limit": req.daily_job_limit,
            "max_storage_mb": req.max_storage_mb,
            "webhook_configured": bool(webhook_url),
        },
    )
    return _policy_out(db, service_name)


@router.get("/service-policies/{service_name}/webhook-secret")
def get_webhook_secret(
    service_name: str,
    principal: Principal = Depends(require_scope("admin:keys")),
    db: Session = Depends(get_db),
):
    _require_bootstrap_admin(principal)
    if not db.scalar(select(ApiKey).where(ApiKey.name == service_name)):
        raise HTTPException(status_code=404, detail="Service API key not found")
    return {"service_name": service_name, "webhook_secret": derive_webhook_secret(service_name)}


@router.get("/webhook-deliveries", response_model=list[WebhookDeliveryOut])
def list_webhook_deliveries(
    status: str | None = Query(default=None, pattern=r"^(queued|retrying|delivered|dead)$"),
    service_name: str | None = Query(default=None, max_length=120),
    limit: int = Query(default=200, ge=1, le=2000),
    _: Principal = Depends(require_scope("admin:keys")),
    db: Session = Depends(get_db),
):
    stmt = select(WebhookDelivery).order_by(desc(WebhookDelivery.created_at)).limit(limit)
    if status:
        stmt = stmt.where(WebhookDelivery.status == status)
    if service_name:
        stmt = stmt.where(WebhookDelivery.service_name == service_name)
    return db.scalars(stmt).all()


@router.post("/webhook-deliveries/{delivery_id}/retry", response_model=WebhookDeliveryOut)
def retry_webhook_delivery(
    delivery_id: str,
    principal: Principal = Depends(require_scope("admin:keys")),
    db: Session = Depends(get_db),
):
    delivery = db.get(WebhookDelivery, delivery_id)
    if not delivery:
        raise HTTPException(status_code=404, detail="Webhook delivery not found")
    if delivery.status != "dead":
        raise HTTPException(status_code=409, detail="Only dead-letter webhook deliveries can be retried")
    _require_admin_action_audit(
        "webhook.requeue_requested", principal, "webhook_delivery", delivery.id,
        {"status": delivery.status},
    )
    try:
        return retry_dead_webhook(db, delivery, principal.name)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit")
def audit_log(
    limit: int = Query(default=200, ge=1, le=2000),
    _: Principal = Depends(require_scope("admin:keys")),
):
    return read_audit_events(limit)
