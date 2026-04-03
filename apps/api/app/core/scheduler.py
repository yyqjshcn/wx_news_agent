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
from app.models.rss_feed import RssFeed
from app.core.security import decrypt_api_key
from app.services.rss_service import parse_feed

logger = logging.getLogger(__name__)

WECHAT_ADAPTER_URL = "http://wechat-adapter:5000"


def _get_settings():
    return get_settings()


def _ensure_tz(dt: datetime | None) -> datetime | None:
    """Ensure datetime is timezone-aware (UTC)."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


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
        started_at = _ensure_tz(run.started_at)
        if started_at:
            run.duration_ms = int((finished_at - started_at).total_seconds() * 1000)

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


async def _fetch_article_content(url: str) -> dict:
    """Fetch full article content via WeChat adapter POST /api/article."""
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{WECHAT_ADAPTER_URL}/api/article",
                json={"url": url},
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("success") and data.get("data"):
                return {
                    "plain_content": data["data"].get("plain_content", ""),
                    "html_content": data["data"].get("content", ""),
                }
            return {"plain_content": "", "html_content": "", "error": data.get("error", "No content returned")}
    except Exception as e:
        logger.warning(f"Failed to fetch article content from {url}: {e}")
        return {"plain_content": "", "html_content": "", "error": str(e)}


async def _fetch_rss_article_content(url: str) -> dict:
    """Fetch full article content from an RSS article URL."""
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            html = resp.text
            
            from lxml import html as lxml_html
            tree = lxml_html.fromstring(html)
            
            # Remove script and style elements
            for el in tree.xpath("//script|//style|//nav|//footer|//header|//aside"):
                el.getparent().remove(el, ignore_already_removed=True)
            
            # Try to find main content area
            content_el = tree.xpath("//article") or tree.xpath("//main") or tree.xpath("//div[contains(@class, 'content')]") or tree.xpath("//div[contains(@class, 'article')]") or tree.xpath("//div[contains(@class, 'post')]") or tree.xpath("//body")
            if content_el:
                text = content_el[0].text_content()
            else:
                text = tree.text_content()
            
            # Clean up whitespace
            lines = [line.strip() for line in text.split("\n") if line.strip()]
            plain_text = "\n".join(lines)
            
            return {
                "plain_content": plain_text[:10000],
                "html_content": html[:50000],
            }
    except Exception as e:
        logger.warning(f"Failed to fetch RSS article content from {url}: {e}")
        return {"plain_content": "", "html_content": "", "error": str(e)}


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

                    # Fetch full article content
                    plain_content = digest
                    html_content = None
                    if link:
                        content_result = await _fetch_article_content(link)
                        if content_result.get("plain_content"):
                            plain_content = content_result["plain_content"]
                        if content_result.get("html_content"):
                            html_content = content_result["html_content"]

                    new_article = RawArticle(
                        id=str(hashlib.md5(link.encode()).hexdigest()),
                        article_url=link,
                        title=title,
                        account_name=account.account_name,
                        source_type="wechat",
                        fakeid=account.fakeid,
                        publish_time=publish_time,
                        author=author or None,
                        plain_content=plain_content,
                        html_content=html_content,
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
    session = async_session()
    try:
        BATCH_SIZE = 10
        total_classified = 0
        total_errors = []

        result = await session.execute(
            select(LlmProvider).where(
                LlmProvider.enabled == True,
                LlmProvider.is_default_for_extraction == True,
            )
        )
        provider = result.scalar_one_or_none()

        if not provider:
            result = await session.execute(
                select(LlmProvider).where(LlmProvider.enabled == True)
            )
            provider = result.scalar_one_or_none()

        if not provider:
            return {
                "workflow_id": workflow_id,
                "classified_count": 0,
                "message": "No enabled LLM provider found",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        while True:
            result = await session.execute(
                select(RawArticle).where(
                    RawArticle.status == "new",
                ).order_by(RawArticle.created_at.asc()).limit(BATCH_SIZE)
            )
            articles = result.scalars().all()

            if not articles:
                break

            errors = []
            semaphore = asyncio.Semaphore(3)

            async def classify_one(article):
                async with semaphore:
                    try:
                        classification = await _classify_article_async(article, provider)
                        
                        article.is_relevant = classification.get("is_relevant")
                        article.relevance_score = classification.get("relevance_score")
                        article.primary_event_type = classification.get("event_type")
                        article.tags_json = classification.get("tags", [])
                        article.companies_json = classification.get("companies", [])
                        article.summary_short = classification.get("summary_short", "")
                        article.summary_long = classification.get("summary_long", "")
                        article.status = "classified"
                        article.updated_at = datetime.now(timezone.utc)

                        if provider:
                            article.llm_provider_id = provider.id
                            article.llm_model = provider.default_model

                        return True, None
                    except Exception as e:
                        return False, f"{article.title[:30]}: {e}"

            tasks = [classify_one(article) for article in articles]
            results = await asyncio.gather(*tasks)

            batch_classified = 0
            for success, error in results:
                if success:
                    batch_classified += 1
                else:
                    errors.append(error)

            total_classified += batch_classified
            total_errors.extend(errors)
            await session.commit()

            logger.info(f"Classified batch: {batch_classified}/{len(articles)} articles")

        return {
            "workflow_id": workflow_id,
            "classified_count": total_classified,
            "total_errors": len(total_errors),
            "errors": total_errors[:10],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    finally:
        await session.close()


async def _classify_article_async(article, provider) -> dict:
    """Classify a single article using LLM (async)."""
    import json
    import httpx
    from app.core.security import decrypt_api_key

    if not provider:
        return {
            "is_relevant": None,
            "relevance_score": 0,
            "event_type": None,
            "tags": [],
            "companies": [],
            "summary_short": article.plain_content[:200] if article.plain_content else "",
            "summary_long": "",
        }

    api_key = decrypt_api_key(provider.api_key_encrypted)
    url = provider.base_url.rstrip("/") + "/chat/completions"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if provider.extra_headers_json:
        headers.update(provider.extra_headers_json)

    content = article.plain_content or article.title or ""
    content_limit = int(len(content) * 0.8)
    content_for_llm = content[:content_limit] if content_limit > 0 else content

    prompt = (
        f"请分析以下微信公众号文章，返回JSON格式的分类结果。\n\n"
        f"文章标题: {article.title}\n"
        f"来源公众号: {article.account_name}\n"
        f"文章内容: {content_for_llm}\n\n"
        "请返回以下JSON格式（不要其他内容）：\n"
        "{\n"
        '  "is_relevant": true/false,  // 是否与具身智能/AI/机器人领域相关\n'
        '  "relevance_score": 1-10,    // 相关性评分\n'
        '  "event_type": "string",     // 事件类型：融资/发布/合作/展会/研究/政策/其他\n'
        '  "tags": ["tag1", "tag2"],   // 关键词标签，最多5个\n'
        '  "companies": ["公司1"],     // 文中提到的公司名称，最多10个\n'
        '  "summary_short": "一句话摘要",\n'
        '  "summary_long": "详细摘要，3-5句话"\n'
        "}"
    )

    payload = {
        "model": provider.default_model,
        "messages": [
            {"role": "system", "content": "你是一个专业的科技文章分类助手。请严格按照要求的JSON格式返回结果，不要添加任何其他内容。"},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": 2000,
        "temperature": 0.1,
    }

    for attempt in range(provider.max_retries):
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                content_str = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                
                # Extract JSON from response
                content_str = content_str.strip()
                if content_str.startswith("```"):
                    content_str = content_str.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
                
                result = json.loads(content_str)
                return {
                    "is_relevant": result.get("is_relevant"),
                    "relevance_score": result.get("relevance_score", 0),
                    "event_type": result.get("event_type"),
                    "tags": result.get("tags", [])[:5],
                    "companies": result.get("companies", [])[:10],
                    "summary_short": result.get("summary_short", ""),
                    "summary_long": result.get("summary_long", ""),
                }
        except Exception as e:
            if attempt == provider.max_retries - 1:
                logger.error(f"LLM classification failed: {e}")
                return {
                    "is_relevant": None,
                    "relevance_score": 0,
                    "event_type": None,
                    "tags": [],
                    "companies": [],
                    "summary_short": article.plain_content[:200] if article.plain_content else "",
                    "summary_long": "",
                }
            import asyncio
            await asyncio.sleep(2 ** attempt)

    return {
        "is_relevant": None,
        "relevance_score": 0,
        "event_type": None,
        "tags": [],
        "companies": [],
        "summary_short": "",
        "summary_long": "",
    }


async def do_rss_ingest(workflow_id: str) -> dict:
    """Fetch articles from RSS feeds and store them."""
    session = async_session()
    try:
        result = await session.execute(
            select(RssFeed).where(
                RssFeed.enabled == True,
            )
        )
        feeds = result.scalars().all()

        if not feeds:
            return {
                "workflow_id": workflow_id,
                "status": "completed",
                "articles_fetched": 0,
                "articles_stored": 0,
                "message": "No enabled RSS feeds",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        result = await session.execute(
            select(Keyword).where(Keyword.enabled == True)
        )
        keywords = result.scalars().all()
        keyword_texts = [k.keyword.lower() for k in keywords]

        total_fetched = 0
        total_stored = 0
        total_matched = 0
        errors = []

        for feed in feeds:
            try:
                feed_result = parse_feed(feed.feed_url)
                if not feed_result["success"]:
                    errors.append(f"{feed.name}: {feed_result.get('error')}")
                    feed.last_checked_at = datetime.now(timezone.utc)
                    await session.commit()
                    continue

                entries = feed_result.get("entries", [])
                total_fetched += len(entries)

                for entry in entries:
                    link = entry.get("link", "")
                    if not link:
                        continue

                    content_text = (entry.get("title", "") + " " + entry.get("content", "")).lower()
                    matched = not keyword_texts or any(
                        kw in content_text for kw in keyword_texts
                    )
                    if matched:
                        total_matched += 1

                    content_hash = hashlib.sha256(
                        (entry.get("title", "") + link).encode()
                    ).hexdigest()

                    existing_result = await session.execute(
                        select(RawArticle).where(RawArticle.article_url == link)
                    )
                    existing = existing_result.scalar_one_or_none()
                    if existing:
                        continue

                    # Fetch full article content
                    rss_content = entry.get("content", "")
                    plain_content = rss_content
                    html_content = None
                    if link:
                        content_result = await _fetch_rss_article_content(link)
                        if content_result.get("plain_content"):
                            plain_content = content_result["plain_content"]
                        if content_result.get("html_content"):
                            html_content = content_result["html_content"]

                    new_article = RawArticle(
                        id=str(hashlib.md5(link.encode()).hexdigest()),
                        article_url=link,
                        title=entry.get("title", "Untitled"),
                        account_name=feed.name,
                        source_type="rss",
                        fakeid=None,
                        publish_time=entry.get("published"),
                        author=entry.get("author") or None,
                        plain_content=plain_content,
                        html_content=html_content,
                        content_hash=content_hash,
                        status="new",
                        is_relevant=matched if keyword_texts else None,
                    )
                    session.add(new_article)
                    total_stored += 1

                feed.last_checked_at = datetime.now(timezone.utc)
                feed.last_success_at = datetime.now(timezone.utc)
                await session.commit()

            except Exception as e:
                logger.error(f"Failed to fetch RSS feed {feed.name}: {e}")
                errors.append(f"{feed.name}: {e}")
                feed.last_checked_at = datetime.now(timezone.utc)
                await session.commit()

        return {
            "workflow_id": workflow_id,
            "status": "completed",
            "articles_fetched": total_fetched,
            "articles_stored": total_stored,
            "articles_matched_keyword": total_matched,
            "sources_processed": len(feeds),
            "errors": errors[:5],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    finally:
        await session.close()


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
    WorkflowType.RSS_INGEST: do_rss_ingest,
}


async def run_workflow_task(workflow_id: str, trigger_type: TriggerType = TriggerType.SCHEDULED):
    """Execute a workflow task by ID."""
    session = async_session()
    try:
        workflow = await session.get(Workflow, workflow_id)
        if not workflow:
            logger.error(f"Workflow {workflow_id} not found")
            return

        task_fn = TASK_MAP.get(workflow.workflow_type)
        if not task_fn:
            logger.error(f"No task mapped for workflow type: {workflow.workflow_type}")
            return

        run_id = str(uuid.uuid4())

        run = WorkflowRun(
            id=run_id,
            workflow_id=workflow_id,
            trigger_type=trigger_type.value,
            status=WorkflowRunStatus.PENDING,
        )
        session.add(run)
        await session.commit()
    finally:
        await session.close()

    try:
        await _execute_workflow(run_id, workflow.workflow_type.value, task_fn)
    except Exception as e:
        logger.error(f"Workflow {workflow_id} execution failed: {e}")


# Global scheduler instance
_scheduler: AsyncIOScheduler | None = None


def get_scheduler():
    """Create and configure the APScheduler instance."""
    scheduler = AsyncIOScheduler()

    settings = _get_settings()

    return scheduler


def get_current_scheduler() -> AsyncIOScheduler | None:
    """Get the current running scheduler instance."""
    return _scheduler


async def _add_workflow_job(scheduler: AsyncIOScheduler, workflow: Workflow):
    """Add a single workflow job to the scheduler."""
    if not workflow.cron_expression:
        logger.warning(f"Workflow '{workflow.workflow_name}' has no cron expression, skipping")
        return False

    parts = workflow.cron_expression.split()
    if len(parts) != 5:
        logger.warning(f"Invalid cron expression for {workflow.workflow_name}: {workflow.cron_expression}")
        return False

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
    return True


async def _load_workflows_to_scheduler(scheduler: AsyncIOScheduler):
    """Load all enabled workflows from database to scheduler."""
    session = async_session()
    try:
        result = await session.execute(
            select(Workflow).where(Workflow.enabled == True)
        )
        workflows = result.scalars().all()

        for workflow in workflows:
            await _add_workflow_job(scheduler, workflow)
    finally:
        await session.close()


async def reload_scheduler_workflows(scheduler: AsyncIOScheduler | None = None):
    """Reload all workflow schedules from database.
    
    This function can be called to dynamically refresh the scheduler
    when workflows are modified via API.
    """
    if scheduler is None:
        scheduler = _scheduler
    
    if not scheduler or not scheduler.running:
        logger.warning("Scheduler is not running, cannot reload workflows")
        return

    logger.info("Reloading workflow schedules from database...")
    
    session = async_session()
    try:
        # Get all enabled workflows from database
        result = await session.execute(
            select(Workflow).where(Workflow.enabled == True)
        )
        workflows = result.scalars().all()
        workflow_map = {w.id: w for w in workflows}
        
        # Get current workflow jobs
        current_job_ids = {
            job.id for job in scheduler.get_jobs()
            if job.id.startswith("workflow_")
        }
        current_workflow_ids = {
            job.id.replace("workflow_", "") for job in scheduler.get_jobs()
            if job.id.startswith("workflow_")
        }
        
        # Remove jobs for disabled or deleted workflows
        for job_id in current_job_ids:
            workflow_id = job_id.replace("workflow_", "")
            if workflow_id not in workflow_map:
                scheduler.remove_job(job_id)
                logger.info(f"Removed job {job_id} (workflow disabled or deleted)")
        
        # Add or update jobs for enabled workflows
        for workflow in workflows:
            job_id = f"workflow_{workflow.id}"
            existing_job = scheduler.get_job(job_id)
            
            if existing_job:
                # Check if cron expression or timezone changed
                # We need to compare the trigger settings
                current_trigger = existing_job.trigger
                parts = workflow.cron_expression.split()
                if len(parts) == 5:
                    minute, hour, day, month, day_of_week = parts
                    # If trigger differs, remove and re-add
                    if (current_trigger.fields[0].__str__() != minute or
                        current_trigger.fields[1].__str__() != hour or
                        current_trigger.fields[2].__str__() != day or
                        current_trigger.fields[3].__str__() != month or
                        current_trigger.fields[4].__str__() != day_of_week):
                        scheduler.remove_job(job_id)
                        await _add_workflow_job(scheduler, workflow)
                        logger.info(f"Updated job {job_id} (cron expression changed)")
            else:
                # New workflow, add it
                await _add_workflow_job(scheduler, workflow)
        
        logger.info(f"Workflow reload complete. Total jobs: {len([j for j in scheduler.get_jobs() if j.id.startswith('workflow_')])}")
    finally:
        await session.close()


async def add_workflow_to_scheduler(workflow_id: str):
    """Add a single workflow to the scheduler.
    
    Called when a new workflow is created.
    """
    global _scheduler
    if not _scheduler or not _scheduler.running:
        logger.warning("Scheduler is not running, cannot add workflow")
        return
    
    session = async_session()
    try:
        workflow = await session.get(Workflow, workflow_id)
        if not workflow or not workflow.enabled:
            logger.warning(f"Workflow {workflow_id} not found or disabled")
            return
        
        await _add_workflow_job(_scheduler, workflow)
    finally:
        await session.close()


async def remove_workflow_from_scheduler(workflow_id: str):
    """Remove a workflow from the scheduler.
    
    Called when a workflow is deleted or disabled.
    """
    global _scheduler
    if not _scheduler or not _scheduler.running:
        logger.warning("Scheduler is not running, cannot remove workflow")
        return
    
    job_id = f"workflow_{workflow_id}"
    try:
        _scheduler.remove_job(job_id)
        logger.info(f"Removed job {job_id}")
    except Exception as e:
        logger.warning(f"Failed to remove job {job_id}: {e}")


async def update_workflow_in_scheduler(workflow_id: str):
    """Update a workflow in the scheduler.
    
    Called when a workflow is updated (cron expression, enabled status, etc.)
    """
    global _scheduler
    if not _scheduler or not _scheduler.running:
        logger.warning("Scheduler is not running, cannot update workflow")
        return
    
    session = async_session()
    try:
        workflow = await session.get(Workflow, workflow_id)
        if not workflow:
            # Workflow deleted, remove from scheduler
            await remove_workflow_from_scheduler(workflow_id)
            return
        
        job_id = f"workflow_{workflow_id}"
        existing_job = _scheduler.get_job(job_id)
        
        if not workflow.enabled:
            # Workflow disabled, remove from scheduler
            if existing_job:
                await remove_workflow_from_scheduler(workflow_id)
            return
        
        # Workflow enabled, add or update
        if existing_job:
            # Remove old job and add new one (in case cron changed)
            _scheduler.remove_job(job_id)
        
        await _add_workflow_job(_scheduler, workflow)
    finally:
        await session.close()


async def start_scheduler():
    """Initialize scheduler with workflow schedules from database."""
    global _scheduler
    _scheduler = get_scheduler()

    await _load_workflows_to_scheduler(_scheduler)

    _scheduler.start()
    logger.info(f"Scheduler started with {len(_scheduler.get_jobs())} jobs")
    
    # Store the event loop reference for the reload job
    _event_loop = asyncio.get_event_loop()
    
    # Define a wrapper function for the periodic reload job
    def reload_wrapper():
        try:
            # Use the stored event loop to create task
            if _event_loop.is_running():
                # Use call_soon_threadsafe to schedule from another thread
                _event_loop.call_soon_threadsafe(
                    lambda: asyncio.create_task(reload_scheduler_workflows(_scheduler))
                )
        except Exception as e:
            logger.error(f"Error in reload_wrapper: {e}")
    
    # Add a periodic reload job to check for workflow changes every 60 seconds
    _scheduler.add_job(
        reload_wrapper,
        "interval",
        seconds=60,
        id="reload_workflows",
        name="Reload workflow schedules",
        replace_existing=True,
    )
    logger.info("Added periodic workflow reload job (every 60 seconds)")
    
    return _scheduler


async def stop_scheduler(scheduler):
    """Shutdown the scheduler."""
    global _scheduler
    if scheduler and scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")
    _scheduler = None
