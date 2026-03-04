from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    ENVIRONMENT: Literal["local", "dev", "prod"] = "local"
    LOG_LEVEL: str
    DATABASE_URL: str
    CANDIDATE_SERVICE_URL: str
    SEARCH_SERVICE_URL: str
    CIRCUIT_BREAKER_FAILURE_THRESHOLD: int
    CIRCUIT_BREAKER_RECOVERY_TIMEOUT: int
    RATE_LIMIT_DEFAULT: str
    SECRET_KEY: str
    ALGORITHM: str

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()