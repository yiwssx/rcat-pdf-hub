from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PDFHUB_", case_sensitive=False)

    database_url: str = "postgresql+psycopg://pdfhub:pdfhub@postgres:5432/pdfhub"
    redis_url: str = "redis://valkey:6379/0"
    gotenberg_url: str = "http://gotenberg:3000"
    data_dir: Path = Path("/data")
    max_upload_mb: int = 100
    retention_hours: int = 24
    cleanup_interval_seconds: int = 900
    cleanup_temporary_hours: int = 6
    preview_max_width: int = 1600

    default_rate_limit_per_minute: int = 120
    default_daily_job_limit: int = 1000
    default_max_storage_mb: int = 2048

    webhook_allowed_hosts: str = ""
    webhook_master_secret: str = Field(default="change-me-webhook-master-secret", min_length=16)
    webhook_timeout_seconds: int = 10

    api_key_pepper: str = Field(default="change-me", min_length=8)
    admin_api_key: str = Field(default="change-me-now", min_length=12)
    allowed_origins: str = "http://localhost:8080"

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def origins(self) -> list[str]:
        return [x.strip() for x in self.allowed_origins.split(",") if x.strip()]

    @property
    def webhook_hosts(self) -> list[str]:
        return [x.strip().lower() for x in self.webhook_allowed_hosts.split(",") if x.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
