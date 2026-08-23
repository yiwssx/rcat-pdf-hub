import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import ApiKey
from app.schemas import ApiKeyCreate, ApiKeyCreated, ApiKeyOut
from app.security import Principal, hash_api_key, new_api_key, require_scope

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

ALLOWED_SCOPES = {
    "files:read", "files:write", "jobs:read",
    "pdf:merge", "pdf:split", "pdf:rotate", "pdf:compress",
    "pdf:ocr", "pdf:pdfa", "pdf:convert", "admin:keys",
}


def _out(record: ApiKey) -> ApiKeyOut:
    return ApiKeyOut(id=record.id, name=record.name, scopes=json.loads(record.scopes_json), active=record.active)


@router.get("/api-keys", response_model=list[ApiKeyOut])
def list_api_keys(
    _: Principal = Depends(require_scope("admin:keys")),
    db: Session = Depends(get_db),
):
    return [_out(record) for record in db.scalars(select(ApiKey).order_by(ApiKey.name)).all()]


@router.post("/api-keys", response_model=ApiKeyCreated)
def create_api_key(
    req: ApiKeyCreate,
    _: Principal = Depends(require_scope("admin:keys")),
    db: Session = Depends(get_db),
):
    invalid = sorted(set(req.scopes) - ALLOWED_SCOPES)
    if invalid:
        raise HTTPException(status_code=422, detail={"invalid_scopes": invalid})
    if db.scalar(select(ApiKey).where(ApiKey.name == req.name)):
        raise HTTPException(status_code=409, detail="API key name already exists")
    secret = new_api_key()
    record = ApiKey(name=req.name, key_hash=hash_api_key(secret), scopes_json=json.dumps(sorted(set(req.scopes))))
    db.add(record)
    db.commit()
    db.refresh(record)
    return ApiKeyCreated(id=record.id, name=record.name, api_key=secret, scopes=sorted(set(req.scopes)))


@router.delete("/api-keys/{key_id}", response_model=ApiKeyOut)
def revoke_api_key(
    key_id: str,
    _: Principal = Depends(require_scope("admin:keys")),
    db: Session = Depends(get_db),
):
    record = db.get(ApiKey, key_id)
    if not record:
        raise HTTPException(status_code=404, detail="API key not found")
    record.active = False
    db.commit()
    db.refresh(record)
    return _out(record)
