from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "file-service"
    app_version: str = "0.1.0"
    app_env: str = "dev"
    debug: bool = False

    host: str = "0.0.0.0"
    port: int = 8000

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/files"
    sql_echo: bool = False
    db_pool_size: int = 20
    db_max_overflow: int = 40
    db_pool_pre_ping: bool = True

    s3_endpoint_url: str = "http://localhost:9000"
    s3_public_endpoint_url: str | None = None
    ngrok_api_url: str | None = None
    ngrok_tunnel_addr_contains: str | None = None
    s3_public_endpoint_discovery_timeout_seconds: int = 90
    s3_public_endpoint_discovery_poll_interval_seconds: float = 2.0
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_region: str = "us-east-1"
    s3_bucket_name: str = "files"
    s3_force_path_style: bool = True

    default_upload_url_expiration_seconds: int = 3600
    default_download_url_expiration_seconds: int = 3600

    pending_upload_ttl_seconds: int = 3600
    pending_cleanup_batch_size: int = 100
    pending_cleanup_poll_interval_seconds: float = 60.0

    internal_service_token: str | None = None

    rabbitmq_url: str = "amqp://guest:guest@localhost:5672/"
    rabbitmq_exchange: str = "file.events"
    rabbitmq_cleanup_queue: str = "file.cleanup.requested.queue"
    rabbitmq_cleanup_routing_key: str = "file.cleanup.requested"
    outbox_batch_size: int = 100
    outbox_poll_interval_seconds: float = 1.0
    outbox_max_retries: int = 10

    log_level: str = "INFO"
    log_json: bool = True

    request_id_header_name: str = "X-Request-ID"
    expose_request_id_header: bool = True

    idempotency_enabled: bool = True
    idempotency_header_name: str = "Idempotency-Key"

    swagger_enabled: bool = True
    metrics_enabled: bool = True
    docs_url: str | None = "/docs"
    redoc_url: str | None = "/redoc"
    openapi_url: str | None = "/openapi.json"

    cors_allow_origins: list[str] = Field(default_factory=list)
    cors_allow_credentials: bool = True
    cors_allow_methods: list[str] = Field(default_factory=lambda: ["*"])
    cors_allow_headers: list[str] = Field(default_factory=lambda: ["*"])

    max_filename_length: int = 255
    max_content_type_length: int = 255
    max_object_key_length: int = 1024

    allowed_image_content_types: tuple[str, ...] = (
        "image/jpeg",
        "image/png",
        "image/webp",
    )
    allowed_resume_content_types: tuple[str, ...] = (
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )

    @field_validator("s3_endpoint_url", mode="before")
    @classmethod
    def normalize_s3_endpoint_url(cls, value: str) -> str:
        if not isinstance(value, str):
            raise ValueError("s3_endpoint_url must be a string")

        normalized = value.strip().rstrip("/")
        if not normalized:
            raise ValueError("s3_endpoint_url must not be empty")

        return normalized

    @field_validator("s3_public_endpoint_url", mode="before")
    @classmethod
    def normalize_s3_public_endpoint_url(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return None

        if not isinstance(value, str):
            raise ValueError("s3_public_endpoint_url must be a string")

        normalized = value.strip().rstrip("/")
        return normalized or None

    @field_validator("ngrok_api_url", mode="before")
    @classmethod
    def normalize_ngrok_api_url(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return None

        if not isinstance(value, str):
            raise ValueError("ngrok_api_url must be a string")

        normalized = value.strip().rstrip("/")
        return normalized or None

    @field_validator("ngrok_tunnel_addr_contains", mode="before")
    @classmethod
    def normalize_ngrok_tunnel_addr_contains(cls, value: str | None) -> str | None:
        if value is None:
            return None

        if not isinstance(value, str):
            raise ValueError("ngrok_tunnel_addr_contains must be a string")

        normalized = value.strip()
        return normalized or None

    @field_validator("cors_allow_origins", mode="before")
    @classmethod
    def parse_cors_allow_origins(cls, value):
        if value is None or value == "":
            return []

        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]

        if isinstance(value, list):
            return value

        raise ValueError("cors_allow_origins must be a list or comma-separated string")

    @field_validator("log_level", mode="before")
    @classmethod
    def normalize_log_level(cls, value: str) -> str:
        if not isinstance(value, str):
            raise ValueError("log_level must be a string")
        return value.strip().upper()

    @field_validator("s3_public_endpoint_discovery_timeout_seconds")
    @classmethod
    def validate_positive_timeout_seconds(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("s3_public_endpoint_discovery_timeout_seconds must be positive")
        return value

    @field_validator("s3_public_endpoint_discovery_poll_interval_seconds")
    @classmethod
    def validate_positive_poll_interval_seconds(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("s3_public_endpoint_discovery_poll_interval_seconds must be positive")
        return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
