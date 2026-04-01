from celery import Celery
from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "embodied_news",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)
