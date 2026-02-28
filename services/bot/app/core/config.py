from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """Конфигурация приложения."""
    TELEGRAM_BOT_TOKEN: str 
    ADMIN_IDS: str
    INTERNAL_BOT_SECRET: str
    AUTH_SERVICE_URL: str
    CANDIDATE_SERVICE_URL: str
    EMPLOYER_SERVICE_URL: str
    SEARCH_SERVICE_URL: str
    FILE_SERVICE_URL: str
    REDIS_HOST: str
    REDIS_PORT: int

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"
    
    @property
    def admin_ids_list(self) -> list[int]:
        return [int(x.strip()) for x in self.ADMIN_IDS.split(",") if x.strip()]

settings = Settings()
ADMIN_IDS = settings.admin_ids_list