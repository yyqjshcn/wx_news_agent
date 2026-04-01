from datetime import datetime, timezone
import logging

from app.db import get_session
from app.models import WorkflowRunStatus, get_workflow, get_workflow_run
from app.worker import celery_app

logger = logging.getLogger(__name__)


def _mark_run_started(run_id: str) -> str:
    with get_session() as session:
        run = get_workflow_run(session, run_id)
        if not run:
            raise ValueError(f"Workflow run not found: {run_id}")
        run.status = WorkflowRunStatus.RUNNING
        run.started_at = datetime.now(timezone.utc)
        session.commit()
        return run.workflow_id


def _mark_run_finished(
    run_id: str,
    status: WorkflowRunStatus,
    summary: dict | None = None,
    error_message: str | None = None,
):
    with get_session() as session:
        run = get_workflow_run(session, run_id)
        if not run:
            raise ValueError(f"Workflow run not found: {run_id}")

        finished_at = datetime.now(timezone.utc)
        run.status = status
        run.finished_at = finished_at
        run.error_message = error_message
        run.summary_json = summary or {}
        if run.started_at:
            run.duration_ms = int((finished_at - run.started_at).total_seconds() * 1000)

        workflow = get_workflow(session, run.workflow_id)
        if workflow:
            workflow.last_run_at = finished_at
            workflow.last_status = status.value
            workflow.updated_at = finished_at

        session.commit()


def _execute_workflow(run_id: str, label: str, payload_factory):
    workflow_id = _mark_run_started(run_id)
    logger.info("Starting %s workflow run %s", label, run_id)
    try:
        result = payload_factory(workflow_id)
        _mark_run_finished(run_id, WorkflowRunStatus.SUCCESS, summary=result)
        return result
    except Exception as e:
        logger.error("%s workflow run %s failed: %s", label, run_id, e)
        _mark_run_finished(
            run_id,
            WorkflowRunStatus.FAILED,
            error_message=str(e),
        )
        raise


@celery_app.task(bind=True, max_retries=3)
def check_wechat_login_health(self, run_id: str):
    try:
        return _execute_workflow(
            run_id,
            "login health check",
            lambda workflow_id: {
                "workflow_id": workflow_id,
                "status": "checked",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )
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
def classify_article(self, run_id: str):
    try:
        return _execute_workflow(
            run_id,
            "classify pending articles",
            lambda workflow_id: {
                "workflow_id": workflow_id,
                "classified_count": 0,
                "is_relevant": False,
                "event_type": None,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )
    except Exception as e:
        logger.error(f"Classification failed: {e}")
        raise self.retry(exc=e, countdown=60)


@celery_app.task(bind=True, max_retries=2)
def generate_daily_digest(self, run_id: str):
    try:
        return _execute_workflow(
            run_id,
            "generate daily digest",
            lambda workflow_id: {
                "workflow_id": workflow_id,
                "digest_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "item_count": 0,
                "content": "# Daily Digest\n\nNo events today.",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )
    except Exception as e:
        logger.error(f"Digest generation failed: {e}")
        raise self.retry(exc=e, countdown=120)


@celery_app.task(bind=True, max_retries=3)
def daily_ingest(self, run_id: str):
    try:
        return _execute_workflow(
            run_id,
            "daily ingest",
            _do_daily_ingest,
        )
    except Exception as e:
        logger.error(f"Daily ingest failed: {e}")
        raise self.retry(exc=e, countdown=300)


WECHAT_ADAPTER_URL = "http://wechat-adapter:5000"


def _do_daily_ingest(workflow_id: str) -> dict:
    import hashlib
    import httpx
    from sqlalchemy import select

    from app.db import get_session
    from app.models import RawArticle, Keyword, SourceAccount

    with get_session() as session:
        accounts = session.execute(
            select(SourceAccount).where(
                SourceAccount.enabled == True,
                SourceAccount.fakeid.isnot(None),
            )
        ).scalars().all()

        keywords = session.execute(
            select(Keyword).where(Keyword.enabled == True)
        ).scalars().all()
        keyword_texts = [k.keyword.lower() for k in keywords]

        if not accounts:
            return {
                "workflow_id": workflow_id,
                "status": "completed",
                "articles_fetched": 0,
                "articles_stored": 0,
                "articles_matched_keyword": 0,
                "message": "No enabled source accounts with fakeid",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        total_fetched = 0
        total_stored = 0
        total_matched = 0
        errors = []

        for account in accounts:
            try:
                articles = _fetch_articles_from_adapter(account.fakeid, count=20)
                total_fetched += len(articles)

                for art in articles:
                    title = art.get("title", "")
                    link = art.get("link", "")
                    author = art.get("author", "")
                    digest = art.get("digest", "")
                    update_time = art.get("update_time")
                    publish_time = None
                    if update_time:
                        publish_time = datetime.fromtimestamp(update_time, tz=timezone.utc)

                    content_text = (title + " " + digest).lower()
                    matched = not keyword_texts or any(
                        kw in content_text for kw in keyword_texts
                    )
                    if matched:
                        total_matched += 1

                    content_hash = hashlib.sha256(
                        (title + link).encode()
                    ).hexdigest()

                    existing = session.execute(
                        select(RawArticle).where(
                            RawArticle.article_url == link
                        )
                    ).scalar_one_or_none()

                    if existing:
                        continue

                    new_article = RawArticle(
                        id=str(hashlib.md5(link.encode()).hexdigest()),
                        article_url=link,
                        title=title,
                        account_name=account.account_name,
                        fakeid=account.fakeid,
                        publish_time=publish_time,
                        author=author or None,
                        plain_content=digest,
                        content_hash=content_hash,
                        status="new",
                        is_relevant=matched if keyword_texts else None,
                    )
                    session.add(new_article)
                    total_stored += 1

                account.last_checked_at = datetime.now(timezone.utc)
                account.last_success_at = datetime.now(timezone.utc)
                session.commit()

            except Exception as e:
                logger.error(f"Failed to fetch articles for {account.account_name}: {e}")
                errors.append(f"{account.account_name}: {e}")
                account.last_checked_at = datetime.now(timezone.utc)
                session.commit()

        return {
            "workflow_id": workflow_id,
            "status": "completed",
            "articles_fetched": total_fetched,
            "articles_stored": total_stored,
            "articles_matched_keyword": total_matched,
            "sources_processed": len(accounts),
            "errors": errors[:5],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


def _fetch_articles_from_adapter(fakeid: str, count: int = 20) -> list:
    import httpx
    resp = httpx.get(
        f"{WECHAT_ADAPTER_URL}/api/public/articles",
        params={"fakeid": fakeid, "begin": 0, "count": count},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("success"):
        return data.get("data", {}).get("articles", [])
    return data.get("list", data.get("articles", []))
