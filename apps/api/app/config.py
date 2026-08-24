from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


DEFAULT_HUMAN_SCOPES = (
    "files:read,files:write,jobs:read,"
    "pdf:merge,pdf:split,pdf:rotate,pdf:compress,pdf:ocr,pdf:pdfa,pdf:convert,"
    "pdf:watermark,pdf:page-number,pdf:stamp,pdf:image-to-pdf,pdf:pdf-to-image,archive:paperless"
)


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
    pdf_to_image_max_pages: int = Field(default=200, ge=1, le=5000)

    default_rate_limit_per_minute: int = 120
    default_daily_job_limit: int = 1000
    default_max_storage_mb: int = 2048

    webhook_allowed_hosts: str = ""
    webhook_allow_private_networks: bool = False
    webhook_master_secret: str = Field(default="change-me-webhook-master-secret", min_length=16)
    webhook_timeout_seconds: int = 10
    webhook_max_attempts: int = Field(default=6, ge=1, le=20)
    webhook_retry_initial_seconds: int = Field(default=5, ge=1, le=3600)
    webhook_retry_max_seconds: int = Field(default=900, ge=1, le=86400)
    webhook_dispatch_interval_seconds: int = Field(default=2, ge=1, le=300)
    webhook_dispatch_batch_size: int = Field(default=50, ge=1, le=1000)

    api_key_pepper: str = Field(default="change-me", min_length=8)
    admin_api_key: str = Field(default="change-me-now", min_length=12)
    allowed_origins: str = "http://localhost:8080"
    public_base_url: str = "http://localhost:8080"

    download_signing_secret: str = Field(
        default="change-me-download-signing-secret-at-least-32-bytes",
        min_length=32,
    )
    signed_download_default_ttl_seconds: int = Field(default=300, ge=30, le=86400)
    signed_download_max_ttl_seconds: int = Field(default=3600, ge=30, le=86400)

    # Human authentication. API keys remain supported for service-to-service calls.
    auth_token_secret: str = Field(default="change-me-auth-token-secret-at-least-32-bytes", min_length=32)
    session_cookie_name: str = "pdfhub_session"
    session_ttl_minutes: int = 480
    session_cookie_secure: bool = False
    human_scopes: str = DEFAULT_HUMAN_SCOPES
    admin_groups: str = "pdfhub-admins"

    # OIDC Authorization Code + PKCE SSO.
    oidc_enabled: bool = False
    oidc_issuer: str = ""
    oidc_client_id: str = ""
    oidc_client_secret: str = ""
    oidc_audience: str = ""
    oidc_discovery_url: str = ""
    oidc_group_claim: str = "groups"
    oidc_scope: str = "openid profile email"
    oidc_state_ttl_seconds: int = 300

    # LDAP credential exchange to a short-lived PDF Hub session.
    ldap_enabled: bool = False
    ldap_url: str = "ldap://ldap:389"
    ldap_base_dn: str = ""
    ldap_bind_dn: str = ""
    ldap_bind_password: str = ""
    ldap_user_filter: str = "(uid={username})"
    ldap_user_dn_template: str = ""
    ldap_group_base_dn: str = ""
    ldap_group_filter: str = "(member={user_dn})"
    ldap_group_attribute: str = "cn"
    ldap_connect_timeout_seconds: int = 5

    # Binary storage. local also covers a NAS mounted at PDFHUB_DATA_DIR.
    storage_backend: Literal["local", "s3"] = "local"
    s3_endpoint_url: str = ""
    s3_region: str = "us-east-1"
    s3_bucket: str = "pdfhub"
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_prefix: str = "pdfhub"
    s3_addressing_style: Literal["path", "virtual"] = "path"
    s3_auto_create_bucket: bool = False
    s3_server_side_encryption: str = ""

    # Malware scanning through clamd INSTREAM.
    clamav_enabled: bool = False
    clamav_host: str = "clamav"
    clamav_port: int = 3310
    clamav_timeout_seconds: int = 30
    clamav_fail_closed: bool = True

    # Queue / horizontal worker tuning.
    rq_queue: str = "pdf"
    rq_job_timeout_seconds: int = 1800

    # Observability.
    prometheus_enabled: bool = True
    otel_endpoint: str = ""
    otel_service_name: str = "rcat-pdf-hub-api"

    # Optional downstream archive.
    paperless_enabled: bool = False
    paperless_url: str = "http://paperless:8000"
    paperless_token: str = ""
    paperless_timeout_seconds: int = 30
    paperless_auto_archive: bool = False

    @model_validator(mode="after")
    def validate_enabled_integrations(self):
        if self.oidc_enabled:
            missing = [
                name for name, value in (
                    ("OIDC_ISSUER", self.oidc_issuer),
                    ("OIDC_CLIENT_ID", self.oidc_client_id),
                ) if not value
            ]
            if missing:
                raise ValueError(f"OIDC enabled but missing: {', '.join(missing)}")
        if self.ldap_enabled and not (self.ldap_user_dn_template or self.ldap_base_dn):
            raise ValueError("LDAP enabled but neither LDAP_USER_DN_TEMPLATE nor LDAP_BASE_DN is configured")
        if self.storage_backend == "s3":
            missing = [
                name for name, value in (
                    ("S3_BUCKET", self.s3_bucket),
                    ("S3_ACCESS_KEY", self.s3_access_key),
                    ("S3_SECRET_KEY", self.s3_secret_key),
                ) if not value
            ]
            if missing:
                raise ValueError(f"S3 storage enabled but missing: {', '.join(missing)}")
        if self.paperless_enabled and not self.paperless_token:
            raise ValueError("Paperless integration enabled but PAPERLESS_TOKEN is empty")
        if self.signed_download_default_ttl_seconds > self.signed_download_max_ttl_seconds:
            raise ValueError("SIGNED_DOWNLOAD_DEFAULT_TTL_SECONDS cannot exceed SIGNED_DOWNLOAD_MAX_TTL_SECONDS")
        return self

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def origins(self) -> list[str]:
        return [x.strip() for x in self.allowed_origins.split(",") if x.strip()]

    @property
    def webhook_hosts(self) -> list[str]:
        return [x.strip().lower() for x in self.webhook_allowed_hosts.split(",") if x.strip()]

    @property
    def human_scope_set(self) -> set[str]:
        return {x.strip() for x in self.human_scopes.split(",") if x.strip()}

    @property
    def admin_group_set(self) -> set[str]:
        return {x.strip() for x in self.admin_groups.split(",") if x.strip()}

    @property
    def oidc_redirect_uri(self) -> str:
        return self.public_base_url.rstrip("/") + "/api/v1/auth/oidc/callback"


@lru_cache
def get_settings() -> Settings:
    return Settings()
