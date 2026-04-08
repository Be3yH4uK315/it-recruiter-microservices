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

    app_name: str = "telegram-bot-service"
    app_version: str = "0.1.0"
    app_env: str = "dev"
    debug: bool = False

    host: str = "0.0.0.0"
    port: int = 8010

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/telegram_bot"
    sql_echo: bool = False
    db_pool_size: int = 20
    db_max_overflow: int = 40
    db_pool_pre_ping: bool = True

    http_client_connect_timeout_seconds: float = 5.0
    http_client_read_timeout_seconds: float = 10.0
    http_client_write_timeout_seconds: float = 10.0
    http_client_pool_timeout_seconds: float = 5.0
    http_client_max_connections: int = 200
    http_client_max_keepalive_connections: int = 50
    http_client_keepalive_expiry_seconds: float = 20.0

    auth_service_url: str = "http://auth:8000"
    candidate_service_url: str = "http://candidate:8000"
    employer_service_url: str = "http://employer:8000"
    search_service_url: str = "http://search:8000"

    internal_service_token: str | None = None

    telegram_bot_token: str | None = None
    telegram_api_base_url: str = "https://api.telegram.org"
    telegram_mode: str = "webhook"
    telegram_webhook_path: str = "/api/v1/telegram/webhook"
    telegram_webhook_url: str | None = None
    telegram_webhook_secret_token: str | None = None

    ngrok_api_url: str | None = None
    telegram_webhook_discovery_timeout_seconds: int = 90
    telegram_webhook_discovery_poll_interval_seconds: float = 2.0

    bot_callback_prefix: str = "ctx:"
    callback_context_ttl_seconds: int = 900
    auth_access_token_refresh_skew_seconds: int = 60

    rate_limit_enabled: bool = True
    rate_limit_messages_per_second: float = 2.0
    rate_limit_callbacks_burst: int = 5
    rate_limit_callbacks_cooldown_seconds: float = 2.0

    request_id_header_name: str = "X-Request-ID"
    expose_request_id_header: bool = True

    swagger_enabled: bool = True
    metrics_enabled: bool = True
    docs_url: str | None = "/docs"
    redoc_url: str | None = "/redoc"
    openapi_url: str | None = "/openapi.json"

    cors_allow_origins: list[str] = Field(default_factory=list)
    cors_allow_credentials: bool = True
    cors_allow_methods: list[str] = Field(default_factory=lambda: ["*"])
    cors_allow_headers: list[str] = Field(default_factory=lambda: ["*"])

    log_level: str = "INFO"
    log_json: bool = True

    @field_validator(
        "auth_service_url",
        "candidate_service_url",
        "employer_service_url",
        "search_service_url",
        "telegram_api_base_url",
        "ngrok_api_url",
        mode="before",
    )
    @classmethod
    def normalize_service_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("service url must be a string")

        normalized = value.strip().rstrip("/")
        return normalized or None

    @field_validator("telegram_webhook_path", mode="before")
    @classmethod
    def normalize_webhook_path(cls, value: str) -> str:
        if not isinstance(value, str):
            raise ValueError("telegram_webhook_path must be a string")
        normalized = value.strip()
        if not normalized:
            raise ValueError("telegram_webhook_path must not be empty")
        if not normalized.startswith("/"):
            normalized = f"/{normalized}"
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

    @field_validator(
        "internal_service_token",
        "telegram_webhook_url",
        "telegram_webhook_secret_token",
        "telegram_bot_token",
        mode="before",
    )
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("telegram_mode", mode="before")
    @classmethod
    def normalize_telegram_mode(cls, value: str) -> str:
        if not isinstance(value, str):
            raise ValueError("telegram_mode must be a string")
        mode = value.strip().lower()
        if mode not in {"webhook", "polling"}:
            raise ValueError("telegram_mode must be either 'webhook' or 'polling'")
        return mode

    @field_validator(
        "callback_context_ttl_seconds",
        "auth_access_token_refresh_skew_seconds",
        "rate_limit_callbacks_burst",
        "telegram_webhook_discovery_timeout_seconds",
    )
    @classmethod
    def validate_positive_int(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("value must be positive")
        return value

    @field_validator(
        "rate_limit_messages_per_second",
        "rate_limit_callbacks_cooldown_seconds",
        "telegram_webhook_discovery_poll_interval_seconds",
    )
    @classmethod
    def validate_positive_float(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("value must be positive")
        return value

    @property
    def uses_placeholder_telegram_bot_token(self) -> bool:
        token = self.telegram_bot_token
        if token is None:
            return False
        return token.startswith("change-me-")

    @property
    def allows_degraded_telegram_webhook_ack(self) -> bool:
        return self.app_env in {"dev", "docker", "test", "local"} and (
            self.uses_placeholder_telegram_bot_token
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
