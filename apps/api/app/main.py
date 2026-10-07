from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import update
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.audit import audit_event
from app.db import Base, SessionLocal, engine
from app.models import FileRecord, JobRecord
from app.observability import install_observability
from app.routers import admin, auth, files, health, integrations, internal, jobs, pdf
from app.storage import ensure_storage

settings = get_settings()


def migrate_legacy_web_console_ownership() -> dict[str, int]:
    if not settings.web_console_auto_login_enabled:
        return {"files": 0, "jobs": 0}
    workspace_id = settings.web_console_workspace_id.strip() or "default"
    stable_name = f"web-console:{workspace_id}"[:120]
    db = SessionLocal()
    try:
        file_result = db.execute(
            update(FileRecord)
            .where(FileRecord.source_system.like("web-console:%"), FileRecord.source_system != stable_name)
            .values(source_system=stable_name)
        )
        job_result = db.execute(
            update(JobRecord)
            .where(JobRecord.requested_by.like("web-console:%"), JobRecord.requested_by != stable_name)
            .values(requested_by=stable_name)
        )
        db.commit()
        result = {"files": int(file_result.rowcount or 0), "jobs": int(job_result.rowcount or 0)}
        if result["files"] or result["jobs"]:
            audit_event("identity.web_console_migrated", "system", "identity", stable_name, result)
        return result
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_storage()
    # Kept as an idempotent safety net for SQLite/unit-test bootstraps. Production
    # deployments run Alembic before Uvicorn through app.entrypoint.
    Base.metadata.create_all(bind=engine)
    migrate_legacy_web_console_ownership()
    yield


app = FastAPI(
    title="PDF Hub API",
    version="0.6.0",
    description="Centralized self-hosted PDF processing, production hardening, secure delivery and integration API",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key"],
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(internal.router)
app.include_router(files.router)
app.include_router(jobs.router)
app.include_router(pdf.router)
app.include_router(integrations.router)
app.include_router(admin.router)

install_observability(app)
