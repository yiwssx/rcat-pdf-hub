import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import audit_event, read_audit_events
from app.config import get_settings
from app.db import get_db
from app.models import ApiKey, ServicePolicy
from app.policy import effective_policy
from app.schemas import ApiKeyCreate, ApiKeyCreated, ApiKeyOut, ServicePolicyOut, ServicePolicyUpdate
from app.security import Principal, hash_api_key, new_api_key, require_scope
from app.webhooks import derive_webhook_secret, validate_webhook_url

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])
settings = get_settings()

ALLOWED_SCOPES = {
    "files:read", "files:write", "jobs:read",
    "pdf:merge", "pdf:split", "pdf:rotate", "pdf:compress",
    "pdf:ocr", "pdf:pdfa", "pdf:convert", "pdf:watermark",
    "pdf:page-number", "pdf:stamp", "admin:keys",
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
    if db.scalar(select(ApiKey).where(ApiKey.name == req.name)):
        raise HTTPException(status_code=409, detail="API key name already exists")

    webhook_url = _validated_webhook(req.webhook_url)
    secret = new_api_key()
    record = ApiKey(name=req.name, key_hash=hash_api_key(secret), scopes_json=json.dumps(sorted(set(req.scopes))))
    policy = ServicePolicy(
        service_name=req.name,
        rate_limit_per_minute=req.rate_limit_per_minute if req.rate_limit_per_minute is not None else settings.default_rate_limit_per_minute,
        daily_job_limit=req.daily_job_limit if req.daily_job_limit is not None else settings.default_daily_job_limit,
        max_storage_mb=req.max_storage_mb if req.max_storage_mb is not None else settings.default_max_storage_mb,
        webhook_url=webhook_url,
    )
    db.add(record)
    db.add(policy)
    db.commit()
    db.refresh(record)
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
    _: Principal = Depends(require_scope("admin:keys")),
    db: Session = Depends(get_db),
):
    if not db.scalar(select(ApiKey).where(ApiKey.name == service_name)):
        raise HTTPException(status_code=404, detail="Service API key not found")
    return {"service_name": service_name, "webhook_secret": derive_webhook_secret(service_name)}


@router.get("/audit")
def audit_log(
    limit: int = Query(default=200, ge=1, le=2000),
    _: Principal = Depends(require_scope("admin:keys")),
):
    return read_audit_events(limit)
