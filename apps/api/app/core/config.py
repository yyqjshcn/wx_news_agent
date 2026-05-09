from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    APP_NAME: str = "omninewsflow"
    APP_ENV: str = "development"
    SECRET_KEY: str = "change-me-to-a-random-string"

    DATABASE_URL: str = "sqlite:///./data/embodied_news.db"
    REDIS_URL: str = "redis://redis:6379/0"

    WECHAT_ADAPTER_URL: str = "http://wechat-adapter:8080"

    ENCRYPTION_KEY: str = "0000000000000000000000000000000000000000000000000000000000000000"

    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = ""
    SMTP_TLS: bool = True

    LOG_LEVEL: str = "INFO"

    WORKFLOW_FAIL_WEBHOOK_URL: str = ""

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
