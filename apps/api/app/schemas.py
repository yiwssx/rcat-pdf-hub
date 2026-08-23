from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

Position = Literal[
    "center",
    "top-left", "top-center", "top-right",
    "bottom-left", "bottom-center", "bottom-right",
]


class FileOut(BaseModel):
    id: str
    original_name: str
    content_type: str
    size: int
    sha256: str
    source_system: str
    created_at: datetime
    expires_at: datetime | None

    model_config = {"from_attributes": True}


class JobOut(BaseModel):
    id: str
    operation: str
    status: str
    progress: int
    input_file_ids: list[str]
    output_file_id: str | None
    params: dict[str, Any]
    error: str | None
    requested_by: str


class MergeRequest(BaseModel):
    file_ids: list[str] = Field(min_length=2, max_length=50)


class SingleFileRequest(BaseModel):
    file_id: str


class SplitRequest(BaseModel):
    file_id: str
    pages: str = Field(pattern=r"^[0-9z,\-]+$")


class RotateRequest(BaseModel):
    file_id: str
    degrees: int = Field(default=90)
    pages: str = Field(default="1-z", pattern=r"^[0-9z,\-]+$")


class OcrRequest(BaseModel):
    file_id: str
    languages: str = Field(default="tha+eng", pattern=r"^[a-z0-9+_-]+$")
    deskew: bool = True
    rotate_pages: bool = True


class WatermarkRequest(BaseModel):
    file_id: str
    text: str = Field(min_length=1, max_length=240)
    font_size: float = Field(default=48, ge=8, le=160)
    opacity: float = Field(default=0.18, ge=0.02, le=1.0)
    rotation: float = Field(default=45, ge=-180, le=180)
    position: Position = "center"
    margin: float = Field(default=36, ge=0, le=240)


class PageNumberRequest(BaseModel):
    file_id: str
    format: str = Field(default="{page} / {total}", min_length=1, max_length=120)
    start_number: int = Field(default=1, ge=0, le=1_000_000)
    font_size: float = Field(default=10, ge=6, le=36)
    position: Position = "bottom-center"
    margin: float = Field(default=24, ge=0, le=240)


class StampRequest(BaseModel):
    file_id: str
    stamp_file_id: str
    position: Position = "bottom-right"
    scale: float = Field(default=0.20, ge=0.03, le=0.80)
    margin: float = Field(default=24, ge=0, le=240)


class ServicePolicyUpdate(BaseModel):
    rate_limit_per_minute: int = Field(ge=0, le=100_000)
    daily_job_limit: int = Field(ge=0, le=10_000_000)
    max_storage_mb: int = Field(ge=0, le=10_000_000)
    webhook_url: str | None = Field(default=None, max_length=2048)


class ServicePolicyOut(BaseModel):
    service_name: str
    rate_limit_per_minute: int
    daily_job_limit: int
    max_storage_mb: int
    webhook_url: str | None


class ApiKeyCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120, pattern=r"^[A-Za-z0-9._-]+$")
    scopes: list[str] = Field(default_factory=lambda: ["files:read", "files:write"])
    rate_limit_per_minute: int | None = Field(default=None, ge=0, le=100_000)
    daily_job_limit: int | None = Field(default=None, ge=0, le=10_000_000)
    max_storage_mb: int | None = Field(default=None, ge=0, le=10_000_000)
    webhook_url: str | None = Field(default=None, max_length=2048)


class ApiKeyCreated(BaseModel):
    id: str
    name: str
    api_key: str
    scopes: list[str]
    policy: ServicePolicyOut
    webhook_secret: str | None = None


class ApiKeyOut(BaseModel):
    id: str
    name: str
    scopes: list[str]
    active: bool
    policy: ServicePolicyOut
