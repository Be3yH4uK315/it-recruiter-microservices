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

    app_name: str = "employer-service"
    app_version: str = "0.1.0"
    app_env: str = "dev"
    debug: bool = False

    host: str = "0.0.0.0"
    port: int = 8000

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/employers"
    sql_echo: bool = False
    db_pool_size: int = 20
    db_max_overflow: int = 40
    db_pool_pre_ping: bool = True

    http_client_connect_timeout_seconds: float = 5.0
    http_client_read_timeout_seconds: float = 5.0
    http_client_write_timeout_seconds: float = 5.0
    http_client_pool_timeout_seconds: float = 5.0
    http_client_max_connections: int = 200
    http_client_max_keepalive_connections: int = 50
    http_client_keepalive_expiry_seconds: float = 20.0

    auth_service_url: str = "http://auth-api:8000"
    candidate_service_url: str = "http://candidate-service:8000"
    search_service_url: str = "http://search-service:8000"
    file_service_url: str = "http://file-api:8000"
    auth_verify_cache_ttl_seconds: int = 15
    auth_verify_cache_max_entries: int = 1024

    internal_service_token: str | None = None

    search_circuit_breaker_failure_threshold: int = 5
    search_circuit_breaker_recovery_timeout_seconds: float = 30.0
    candidate_circuit_breaker_failure_threshold: int = 5
    candidate_circuit_breaker_recovery_timeout_seconds: float = 30.0
    file_circuit_breaker_failure_threshold: int = 5
    file_circuit_breaker_recovery_timeout_seconds: float = 30.0

    rabbitmq_url: str = "amqp://guest:guest@localhost:5672/"
    rabbitmq_exchange: str = "employer.events"
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

    @field_validator(
        "auth_service_url",
        "candidate_service_url",
        "search_service_url",
        "file_service_url",
        mode="before",
    )
    @classmethod
    def normalize_service_url(cls, value: str) -> str:
        if not isinstance(value, str):
            raise ValueError("service url must be a string")

        normalized = value.strip().rstrip("/")
        if not normalized:
            raise ValueError("service url must not be empty")

        return normalized

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


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
