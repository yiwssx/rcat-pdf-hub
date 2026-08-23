from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db import Base, engine
from app.routers import admin, files, health, jobs, pdf
from app.storage import ensure_storage

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_storage()
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="PDF Hub API",
    version="0.2.0",
    description="Centralized self-hosted PDF processing API",
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
app.include_router(files.router)
app.include_router(jobs.router)
app.include_router(pdf.router)
app.include_router(admin.router)
