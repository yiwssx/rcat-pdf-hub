from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PDFHUB_", case_sensitive=False)

    database_url: str = "postgresql+psycopg://pdfhub:pdfhub@postgres:5432/pdfhub"
    redis_url: str = "redis://redis:6379/0"
    gotenberg_url: str = "http://gotenberg:3000"
    data_dir: Path = Path("/data")
    max_upload_mb: int = 100
    retention_hours: int = 24
    api_key_pepper: str = Field(default="change-me", min_length=8)
    admin_api_key: str = Field(default="change-me-now", min_length=12)
    allowed_origins: str = "http://localhost:8080"

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def origins(self) -> list[str]:
        return [x.strip() for x in self.allowed_origins.split(",") if x.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
