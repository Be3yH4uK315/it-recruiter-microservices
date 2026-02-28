from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    ENVIRONMENT: Literal["local", "dev", "prod"] = "local"
    LOG_LEVEL: str
    SECRET_KEY: str
    ALGORITHM: str
    ELASTICSEARCH_URL: str
    CANDIDATE_INDEX_ALIAS: str
    MILVUS_HOST: str
    MILVUS_PORT: str
    MILVUS_COLLECTION_NAME: str
    CANDIDATE_SERVICE_URL: str
    SENTENCE_MODEL_NAME: str
    RANKER_MODEL_NAME: str
    RETRIEVAL_SIZE: int 
    RERANK_TOP_K: int
    RRF_K: int
    FACTOR_NO_SKILLS: float 
    FACTOR_EXP_MISMATCH: float 
    FACTOR_LOCATION_MATCH: float 
    RABBITMQ_HOST: str
    RABBITMQ_PORT: int
    RABBITMQ_USER: str
    RABBITMQ_PASS: str
    CANDIDATE_EXCHANGE_NAME: str
    DLQ_EXCHANGE_NAME: str

    model_config = SettingsConfigDict(
        env_file="./../.env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
