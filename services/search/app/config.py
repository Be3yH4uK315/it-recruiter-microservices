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

    app_name: str = "search-service"
    app_version: str = "0.1.0"
    app_env: str = "dev"
    debug: bool = False

    host: str = "0.0.0.0"
    port: int = 8000

    http_client_timeout_seconds: float = 10.0
    http_client_max_connections: int = 200
    http_client_max_keepalive_connections: int = 50
    http_client_keepalive_expiry_seconds: float = 20.0

    candidate_service_url: str = "http://candidate-service:8000"
    search_service_url: str = "http://search-service:8000"
    internal_service_token: str | None = None

    elasticsearch_url: str = "http://localhost:9200"
    candidate_index_alias: str = "candidates"

    milvus_host: str = "localhost"
    milvus_port: int = 19530
    milvus_collection_name: str = "candidate_embeddings"
    milvus_embedding_dim: int = 384

    sentence_model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    ranker_model_name: str = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"
    ml_concurrency_limit: int = 1

    retrieval_size: int = 100
    rerank_top_k: int = 30
    rrf_k: int = 60
    index_embedding_cache_size: int = 256
    search_result_cache_ttl_seconds: float = 2.0
    search_result_cache_size: int = 128
    search_timing_logging_enabled: bool = False
    search_timing_logging_threshold_ms: float = 1000.0

    factor_no_skills: float = 0.85
    factor_exp_mismatch: float = 0.90
    factor_location_match: float = 1.10

    rabbitmq_url: str = "amqp://guest:guest@localhost:5672/"
    candidate_exchange_name: str = "candidate.events"
    candidate_queue_name: str = "search_service_queue"
    rabbitmq_prefetch_count: int = 1
    rabbitmq_reconnect_delay_seconds: float = 5.0

    log_level: str = "INFO"
    log_json: bool = True

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

    @field_validator(
        "candidate_service_url", "search_service_url", "elasticsearch_url", mode="before"
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
