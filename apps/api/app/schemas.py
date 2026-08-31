from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

Position = Literal[
    "center",
    "top-left", "top-center", "top-right",
    "bottom-left", "bottom-center", "bottom-right",
]
ImagePageSize = Literal["auto", "a4", "letter"]
ImageFit = Literal["contain", "cover"]
RasterFormat = Literal["png", "jpeg"]


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


class ImageToPdfRequest(BaseModel):
    file_ids: list[str] = Field(min_length=1, max_length=100)
    page_size: ImagePageSize = "auto"
    fit: ImageFit = "contain"
    margin: float = Field(default=18, ge=0, le=240)
    dpi: int = Field(default=150, ge=72, le=600)


class PdfToImagesRequest(BaseModel):
    file_id: str
    format: RasterFormat = "png"
    dpi: int = Field(default=150, ge=72, le=600)
    first_page: int = Field(default=1, ge=1, le=100000)
    last_page: int | None = Field(default=None, ge=1, le=100000)


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


class SignedDownloadOut(BaseModel):
    file_id: str
    url: str
    expires_at: datetime


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


class LocalLoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=120, pattern=r"^[^\x00\r\n]+$")
    password: str = Field(min_length=1, max_length=1024)


class LdapLoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=120, pattern=r"^[^\x00\r\n]+$")
    password: str = Field(min_length=1, max_length=1024)


class AuthMeOut(BaseModel):
    name: str
    display_name: str | None
    subject: str | None
    scopes: list[str]
    groups: list[str]
    auth_source: str
    is_admin: bool


class ArchiveOut(BaseModel):
    id: str
    file_id: str
    integration_name: str
    external_id: str | None
    status: str
    error: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WebhookDeliveryOut(BaseModel):
    id: str
    job_id: str
    service_name: str
    url: str
    event: str
    status: str
    attempt_count: int
    max_attempts: int
    next_attempt_at: datetime
    last_error: str | None
    last_status_code: int | None
    created_at: datetime
    updated_at: datetime
    delivered_at: datetime | None

    model_config = {"from_attributes": True}
