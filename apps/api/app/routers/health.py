from fastapi import APIRouter
from redis import Redis
from sqlalchemy import text

from app.config import get_settings
from app.db import SessionLocal

router = APIRouter(tags=["health"])
settings = get_settings()


@router.get("/healthz")
def healthz():
    details = {"database": False, "redis": False}
    with SessionLocal() as db:
        db.execute(text("SELECT 1"))
        details["database"] = True
    Redis.from_url(settings.redis_url).ping()
    details["redis"] = True
    return {"status": "ok", "services": details}
