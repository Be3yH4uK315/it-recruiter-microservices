from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    ENVIRONMENT: Literal["local", "dev", "prod"] = "local"
    LOG_LEVEL: str
    DATABASE_URL: str
    S3_ENDPOINT_URL: str
    S3_PUBLIC_DOMAIN: str
    S3_ACCESS_KEY: str
    S3_SECRET_KEY: str
    S3_BUCKET_NAME: str
    S3_REGION: str
    MAX_FILE_SIZE: int
    SECRET_KEY: str
    ALGORITHM: str

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
