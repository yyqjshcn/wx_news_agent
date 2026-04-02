"""
Background task runner using APScheduler.
Replaces Celery worker + beat for single-instance deployment.
"""
import asyncio
import hashlib
import httpx
import logging
import uuid
from datetime import datetime, timezone, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.database import async_session
from app.models.workflow import Workflow, WorkflowRun, WorkflowRunStatus, TriggerType, WorkflowType
from app.models.source_account import SourceAccount
from app.models.keyword import Keyword
from app.models.article import RawArticle
from app.models.digest import DailyDigest
from app.models.llm_provider import LlmProvider
from app.core.security import decrypt_api_key

logger = logging.getLogger(__name__)

WECHAT_ADAPTER_URL = "http://wechat-adapter:5000"


def _get_settings():
    return get_settings()


async def _get_session() -> AsyncSession:
    return async_session()


async def _mark_run_started(run_id: str) -> str:
    session = async_session()
    try:
        run = await session.get(WorkflowRun, run_id)
        if not run:
            raise ValueError(f"Workflow run not found: {run_id}")
        run.status = WorkflowRunStatus.RUNNING
        run.started_at = datetime.now(timezone.utc)
        await session.commit()
        return run.workflow_id
    finally:
        await session.close()


async def _mark_run_finished(
    run_id: str,
    status: WorkflowRunStatus,
    summary: dict | None = None,
    error_message: str | None = None,
):
    session = async_session()
    try:
        run = await session.get(WorkflowRun, run_id)
        if not run:
            raise ValueError(f"Workflow run not found: {run_id}")

        finished_at = datetime.now(timezone.utc)
        run.status = status
        run.finished_at = finished_at
        run.error_message = error_message
        run.summary_json = summary or {}
        if run.started_at:
            run.duration_ms = int((finished_at - run.started_at).total_seconds() * 1000)

        workflow = await session.get(Workflow, run.workflow_id)
        if workflow:
            workflow.last_run_at = finished_at
            workflow.last_status = status.value
            workflow.updated_at = finished_at
            session.add(workflow)

        await session.commit()
    finally:
        await session.close()


async def _execute_workflow(run_id: str, label: str, payload_factory):
    workflow_id = await _mark_run_started(run_id)
    logger.info("Starting %s workflow run %s", label, run_id)
    try:
        result = await payload_factory(workflow_id)
        await _mark_run_finished(run_id, WorkflowRunStatus.SUCCESS, summary=result)
        return result
    except Exception as e:
        logger.error("%s workflow run %s failed: %s", label, run_id, e)
        await _mark_run_finished(
            run_id,
            WorkflowRunStatus.FAILED,
            error_message=str(e),
        )
        raise


async def _fetch_articles_from_adapter(fakeid: str, count: int = 20) -> list:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{WECHAT_ADAPTER_URL}/api/public/articles",
            params={"fakeid": fakeid, "begin": 0, "count": count},
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("success"):
            return data.get("data", {}).get("articles", [])
        return data.get("list", data.get("articles", []))


async def do_daily_ingest(workflow_id: str) -> dict:
    session = async_session()
    try:
        result = await session.execute(
            select(SourceAccount).where(
                SourceAccount.enabled == True,
                SourceAccount.fakeid.isnot(None),
            )
        )
        accounts = result.scalars().all()

        result = await session.execute(
            select(Keyword).where(Keyword.enabled == True)
        )
        keywords = result.scalars().all()
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
                articles = await _fetch_articles_from_adapter(account.fakeid, count=20)
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

                    existing_result = await session.execute(
                        select(RawArticle).where(RawArticle.article_url == link)
                    )
                    existing = existing_result.scalar_one_or_none()
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
                await session.commit()

            except Exception as e:
                logger.error(f"Failed to fetch articles for {account.account_name}: {e}")
                errors.append(f"{account.account_name}: {e}")
                account.last_checked_at = datetime.now(timezone.utc)
                await session.commit()

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
    finally:
        await session.close()


async def do_classify_articles(workflow_id: str) -> dict:
    return {
        "workflow_id": workflow_id,
        "classified_count": 0,
        "is_relevant": False,
        "event_type": None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


async def do_login_health_check(workflow_id: str) -> dict:
    return {
        "workflow_id": workflow_id,
        "status": "checked",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _fix_markdown_headings(text: str) -> str:
    import re
    lines = text.split("\n")
    fixed = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("##"):
            if i > 0 and fixed and fixed[-1].strip() != "":
                fixed.append("")
            fixed.append(stripped)
            if i < len(lines) - 1 and lines[i + 1].strip() != "":
                fixed.append("")
        else:
            fixed.append(line)
    return "\n".join(fixed)


def _call_llm_sync(provider, system_prompt: str, user_prompt: str, timeout: int | None = None) -> dict:
    import time
    api_key = decrypt_api_key(provider.api_key_encrypted)
    url = provider.base_url.rstrip("/") + "/chat/completions"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if provider.extra_headers_json:
        headers.update(provider.extra_headers_json)

    payload = {
        "model": provider.default_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "max_tokens": 4000,
    }

    effective_timeout = timeout or (provider.request_timeout * 3)

    for attempt in range(provider.max_retries):
        try:
            resp = httpx.post(url, json=payload, headers=headers, timeout=effective_timeout)
            resp.raise_for_status()
            data = resp.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            return {"success": True, "content": content, "usage": data.get("usage", {})}
        except Exception as e:
            if attempt == provider.max_retries - 1:
                return {"success": False, "error": str(e)}
            time.sleep(2 ** attempt)

    return {"success": False, "error": "Max retries exceeded"}


def _generate_digest_content(articles, provider) -> str:
    if not articles:
        return "# 每日摘要\n\n今日暂无相关文章。"

    header = f"# 每日摘要\n\n**日期**: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}\n\n"
    header += f"**共 {len(articles)} 篇文章**\n\n---\n\n"

    if provider:
        try:
            top_articles = articles[:20]
            article_summaries = []
            for i, a in enumerate(top_articles, 1):
                summary = a.summary_short or a.plain_content or ""
                article_summaries.append(
                    f"{i}. **{a.title}**\n"
                    f"   - 来源: {a.account_name}\n"
                    f"   - 链接: {a.article_url}\n"
                    f"   - 摘要: {summary[:150] if summary else '暂无摘要'}"
                )

            prompt = (
                f"以下是今日 {len(articles)} 篇科技文章中最重要的 {len(top_articles)} 篇。\n"
                "请生成一份简洁的每日摘要，包含：\n"
                "1. 一段话概述今日整体动态（3-5句话）\n"
                "2. 按主题分组，每个主题用 `## 主题名称` 标题（前后各空一行），每组2-3句话分析\n"
                "3. 列出相关文章，格式为 `- [标题](链接) — 来源`（每篇文章必须带可点击链接）\n"
                "4. 使用标准 Markdown 格式，中文\n\n"
                "注意：\n"
                "- 每个 `## ` 标题前后必须各空一行\n"
                "- 文章链接必须使用 Markdown 链接格式 `[标题](URL)`\n"
                "- 不要使用 HTML 标签\n\n"
                f"文章：\n\n" + "\n\n".join(article_summaries)
            )

            result = _call_llm_sync(
                provider=provider,
                system_prompt="你是科技新闻编辑助手，擅长从文章中提炼关键趋势，生成简洁的每日摘要。",
                user_prompt=prompt,
                timeout=120,
            )

            if result.get("success"):
                raw = result["content"]
                content = _fix_markdown_headings(raw)
                content = header + content
                footer = f"\n\n---\n\n*摘要由 AI 自动生成，使用模型: {provider.default_model}*"
                return content + footer
            else:
                logger.warning(f"LLM call failed: {result.get('error')}")
        except Exception as e:
            logger.warning(f"LLM digest generation failed, falling back to simple format: {e}")

    content = header
    by_account = {}
    for a in articles:
        by_account.setdefault(a.account_name, []).append(a)

    content += "## 📊 今日概览\n\n"
    content += f"共采集到 **{len(articles)}** 篇文章，来自 **{len(by_account)}** 个公众号。\n\n"

    for account, arts in by_account.items():
        content += f"## {account} ({len(arts)}篇)\n\n"
        for a in arts:
            content += f"- [{a.title}]({a.article_url})"
            if a.summary_short:
                content += f"\n  > {a.summary_short[:150]}"
            content += "\n"
        content += "\n"

    return content


async def do_generate_digest(workflow_id: str) -> dict:
    session = async_session()
    try:
        today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        tomorrow = today + timedelta(days=1)
        yesterday = today - timedelta(days=1)

        result = await session.execute(
            select(RawArticle).where(
                RawArticle.created_at >= today,
                RawArticle.created_at < tomorrow,
                RawArticle.is_relevant == True,
            ).order_by(RawArticle.publish_time.desc())
        )
        articles = result.scalars().all()

        if not articles:
            result = await session.execute(
                select(RawArticle).where(
                    RawArticle.created_at >= today,
                    RawArticle.created_at < tomorrow,
                ).order_by(RawArticle.publish_time.desc()).limit(30)
            )
            articles = result.scalars().all()

        if not articles:
            result = await session.execute(
                select(RawArticle).where(
                    RawArticle.created_at >= yesterday,
                    RawArticle.created_at < today,
                    RawArticle.is_relevant == True,
                ).order_by(RawArticle.publish_time.desc())
            )
            articles = result.scalars().all()

        if not articles:
            result = await session.execute(
                select(RawArticle).where(
                    RawArticle.created_at >= yesterday,
                    RawArticle.created_at < today,
                ).order_by(RawArticle.publish_time.desc()).limit(30)
            )
            articles = result.scalars().all()

        result = await session.execute(
            select(LlmProvider).where(
                LlmProvider.enabled == True,
                LlmProvider.is_default_for_digest == True,
            )
        )
        digest_provider = result.scalar_one_or_none()

        if not digest_provider:
            result = await session.execute(
                select(LlmProvider).where(LlmProvider.enabled == True)
            )
            digest_provider = result.scalar_one_or_none()

        content_md = _generate_digest_content(articles, digest_provider)

        result = await session.execute(
            select(DailyDigest).where(DailyDigest.digest_date == today)
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.content_markdown = content_md
            existing.item_count = len(articles)
            existing.status = "published"
            existing.generated_at = datetime.now(timezone.utc)
            if digest_provider:
                existing.llm_provider_id = digest_provider.id
                existing.llm_model = digest_provider.default_model
            digest = existing
        else:
            digest = DailyDigest(
                id=str(uuid.uuid4()),
                digest_date=today,
                content_markdown=content_md,
                item_count=len(articles),
                status="published",
                generated_at=datetime.now(timezone.utc),
            )
            if digest_provider:
                digest.llm_provider_id = digest_provider.id
                digest.llm_model = digest_provider.default_model
            session.add(digest)

        await session.commit()

        return {
            "workflow_id": workflow_id,
            "digest_date": today.strftime("%Y-%m-%d"),
            "item_count": len(articles),
            "digest_id": digest.id,
            "used_llm": digest_provider is not None,
            "llm_provider": digest_provider.name if digest_provider else None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    finally:
        await session.close()


TASK_MAP = {
    WorkflowType.DAILY_INGEST: do_daily_ingest,
    WorkflowType.MIDDAY_REFRESH: do_daily_ingest,
    WorkflowType.CLASSIFY_PENDING: do_classify_articles,
    WorkflowType.GENERATE_DIGEST: do_generate_digest,
    WorkflowType.RETRY_FAILED: do_daily_ingest,
    WorkflowType.LOGIN_HEALTH_CHECK: do_login_health_check,
}


async def run_workflow_task(workflow_id: str, trigger_type: TriggerType = TriggerType.SCHEDULED):
    """Execute a workflow task by ID."""
    async with _get_session() as session:
        workflow = await session.get(Workflow, workflow_id)
        if not workflow:
            logger.error(f"Workflow {workflow_id} not found")
            return

        task_fn = TASK_MAP.get(workflow.workflow_type)
        if not task_fn:
            logger.error(f"No task mapped for workflow type: {workflow.workflow_type}")
            return

    run_id = str(uuid.uuid4())

    async with _get_session() as session:
        run = WorkflowRun(
            id=run_id,
            workflow_id=workflow_id,
            trigger_type=trigger_type.value,
            status=WorkflowRunStatus.PENDING,
        )
        session.add(run)
        await session.commit()

    try:
        await _execute_workflow(run_id, workflow.workflow_type.value, task_fn)
    except Exception as e:
        logger.error(f"Workflow {workflow_id} execution failed: {e}")


def get_scheduler():
    """Create and configure the APScheduler instance."""
    scheduler = AsyncIOScheduler()

    settings = _get_settings()

    return scheduler


async def start_scheduler():
    """Initialize scheduler with workflow schedules from database."""
    scheduler = get_scheduler()

    session = async_session()
    try:
        result = await session.execute(
            select(Workflow).where(Workflow.enabled == True)
        )
        workflows = result.scalars().all()

        for workflow in workflows:
            if not workflow.cron_expression:
                continue

            parts = workflow.cron_expression.split()
            if len(parts) != 5:
                logger.warning(f"Invalid cron expression for {workflow.workflow_name}: {workflow.cron_expression}")
                continue

            minute, hour, day, month, day_of_week = parts

            trigger = CronTrigger(
                minute=minute,
                hour=hour,
                day=day,
                month=month,
                day_of_week=day_of_week,
                timezone=workflow.timezone or "UTC",
            )

            scheduler.add_job(
                run_workflow_task,
                trigger,
                args=[workflow.id, TriggerType.SCHEDULED],
                id=f"workflow_{workflow.id}",
                name=workflow.workflow_name,
                replace_existing=True,
            )
            logger.info(
                f"Scheduled workflow '{workflow.workflow_name}' ({workflow.id}) "
                f"with cron: {workflow.cron_expression}"
            )
    finally:
        await session.close()

    scheduler.start()
    logger.info(f"Scheduler started with {len(scheduler.get_jobs())} jobs")
    return scheduler


async def stop_scheduler(scheduler):
    """Shutdown the scheduler."""
    if scheduler and scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")
