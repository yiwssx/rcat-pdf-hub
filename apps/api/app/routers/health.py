import httpx
from fastapi import APIRouter, HTTPException
from redis import Redis
from sqlalchemy import text

from app.config import get_settings
from app.db import SessionLocal
from app.integrations.paperless import paperless_health
from app.malware import ping_clamav
from app.observability import refresh_queue_metrics
from app.storage import ensure_storage, s3_client

router = APIRouter(tags=["health"])
settings = get_settings()


def _core_checks() -> dict[str, bool]:
    details = {"database": False, "redis": False}
    with SessionLocal() as db:
        db.execute(text("SELECT 1"))
        details["database"] = True
    Redis.from_url(settings.redis_url).ping()
    details["redis"] = True
    return details


@router.get("/healthz")
def healthz():
    # Liveness/core dependency contract. Worker readiness is handled by /readyz.
    return {"status": "ok", "services": _core_checks()}


@router.get("/readyz")
def readyz():
    services = _core_checks()
    required = dict(services)

    try:
        ensure_storage()
        if settings.storage_backend == "s3":
            s3_client().head_bucket(Bucket=settings.s3_bucket)
        required["storage"] = True
    except Exception:
        required["storage"] = False

    try:
        response = httpx.get(
            settings.gotenberg_url.rstrip("/") + "/health",
            timeout=5.0,
            follow_redirects=False,
        )
        required["gotenberg"] = response.is_success
    except httpx.HTTPError:
        required["gotenberg"] = False

    try:
        _depth, workers = refresh_queue_metrics()
        required["worker"] = workers > 0
    except Exception:
        required["worker"] = False

    if settings.clamav_enabled:
        try:
            required["clamav"] = ping_clamav()
        except Exception:
            required["clamav"] = False

    optional = {"paperless": paperless_health()} if settings.paperless_enabled else {}
    if not all(required.values()):
        raise HTTPException(
            status_code=503,
            detail={"status": "not-ready", "services": required, "optional": optional},
        )
    return {"status": "ready", "services": required, "optional": optional}
