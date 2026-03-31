from celery import Celery
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    REDIS_URL: str = "redis://redis:6379/0"
    DATABASE_URL: str = "postgresql://embodied_news:embodied_news_password@postgres:5432/embodied_news"
    WECHAT_ADAPTER_URL: str = "http://wechat-adapter:8080"

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings():
    return Settings()


settings = get_settings()

celery_app = Celery(
    "embodied_news",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    beat_schedule={
        "daily-ingest": {
            "task": "app.tasks.daily_ingest",
            "schedule": 86400.0,
        },
        "login-health-check": {
            "task": "app.tasks.check_wechat_login_health",
            "schedule": 300.0,
        },
    },
)
