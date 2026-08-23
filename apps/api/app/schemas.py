from typing import Any

from pydantic import BaseModel, Field


class FileOut(BaseModel):
    id: str
    original_name: str
    content_type: str
    size: int
    sha256: str
    source_system: str

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
    pages: str = Field(pattern=r"^[0-9,\-]+$")


class RotateRequest(BaseModel):
    file_id: str
    degrees: int = Field(default=90)
    pages: str = Field(default="1-z", pattern=r"^[0-9z,\-]+$")


class OcrRequest(BaseModel):
    file_id: str
    languages: str = Field(default="tha+eng", pattern=r"^[a-z0-9+_-]+$")
    deskew: bool = True
    rotate_pages: bool = True


class ApiKeyCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120, pattern=r"^[A-Za-z0-9._-]+$")
    scopes: list[str] = Field(default_factory=lambda: ["files:read", "files:write"])


class ApiKeyCreated(BaseModel):
    id: str
    name: str
    api_key: str
    scopes: list[str]


class ApiKeyOut(BaseModel):
    id: str
    name: str
    scopes: list[str]
    active: bool
