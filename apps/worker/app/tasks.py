from app.worker import celery_app
from datetime import datetime, timezone
import logging
import hashlib

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3)
def check_wechat_login_health(self):
    logger.info("Checking WeChat login health")
    try:
        return {"status": "checked", "timestamp": datetime.now(timezone.utc).isoformat()}
    except Exception as e:
        logger.error(f"WeChat health check failed: {e}")
        raise self.retry(exc=e, countdown=60)


@celery_app.task(bind=True, max_retries=3)
def ingest_articles_for_source(self, source_account_id: str):
    logger.info(f"Ingesting articles for source: {source_account_id}")
    try:
        return {
            "source_account_id": source_account_id,
            "articles_fetched": 0,
            "articles_stored": 0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Ingest failed: {e}")
        raise self.retry(exc=e, countdown=120)


@celery_app.task(bind=True, max_retries=2)
def classify_article(self, article_id: str):
    logger.info(f"Classifying article: {article_id}")
    try:
        return {
            "article_id": article_id,
            "is_relevant": False,
            "event_type": None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Classification failed: {e}")
        raise self.retry(exc=e, countdown=60)


@celery_app.task(bind=True, max_retries=2)
def generate_daily_digest(self, digest_date: str = None):
    target_date = digest_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    logger.info(f"Generating daily digest for: {target_date}")
    try:
        return {
            "digest_date": target_date,
            "item_count": 0,
            "content": "# Daily Digest\n\nNo events today.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Digest generation failed: {e}")
        raise self.retry(exc=e, countdown=120)


@celery_app.task(bind=True, max_retries=3)
def daily_ingest(self):
    logger.info("Starting daily ingest workflow")
    try:
        return {
            "status": "completed",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Daily ingest failed: {e}")
        raise self.retry(exc=e, countdown=300)
