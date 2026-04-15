"""
Background task runner using APScheduler.
Replaces Celery worker + beat for single-instance deployment.
"""
import asyncio
import hashlib
import httpx
import logging
import re
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
from app.services import event_service

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

        # Check for WeChat adapter error responses
        ret = data.get("ret")
        if ret is not None and ret != 0:
            msg = data.get("msg", "unknown error")
            raise RuntimeError(f"WeChat adapter error: ret={ret}, msg={msg}")

        if data.get("success"):
            return data.get("data", {}).get("articles", [])
        return data.get("list", data.get("articles", []))


async def _fetch_article_content(url: str, max_retries: int = 3) -> dict:
    """Fetch full article content via WeChat adapter POST /api/article."""
    last_error = None
    for attempt in range(max_retries):
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
                last_error = data.get("error", "No content returned")
                logger.warning(f"WeChat adapter returned no content (attempt {attempt+1}/{max_retries}): {last_error}")
                if last_error and "Rate limited" in str(last_error):
                    # Parse retry delay from rate limit message (e.g., "请13秒后重试")
                    delay_match = re.search(r'请(\d+)秒后重试', str(last_error))
                    if delay_match:
                        delay = int(delay_match.group(1))
                        logger.info(f"Rate limited, waiting {delay}s before retry")
                        await asyncio.sleep(delay)
                        continue
        except Exception as e:
            last_error = str(e)
            logger.warning(f"Failed to fetch article content (attempt {attempt+1}/{max_retries}): {e}")

        if attempt < max_retries - 1:
            wait_time = min(2 ** attempt * 3, 15)
            logger.info(f"Waiting {wait_time}s before retry...")
            await asyncio.sleep(wait_time)

    logger.error(f"Failed to fetch article content after {max_retries} retries: {url} | {last_error}")
    return {"plain_content": "", "html_content": "", "error": last_error}


async def _fetch_rss_article_content(url: str, max_retries: int = 3) -> dict:
    """Fetch full article content from an RSS article URL."""
    last_error = None
    for attempt in range(max_retries):
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
            last_error = str(e)
            logger.warning(f"Failed to fetch RSS article content (attempt {attempt+1}/{max_retries}): {url}: {e}")
            await asyncio.sleep(2 ** attempt)

    logger.error(f"Failed to fetch RSS article content after {max_retries} retries: {url} | {last_error}")
    return {"plain_content": "", "html_content": "", "error": last_error}


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
                    plain_content = digest or title  # fallback: title if digest is empty
                    html_content = None
                    if link:
                        content_result = await _fetch_article_content(link)
                        error = content_result.get("error")
                        if content_result.get("plain_content"):
                            plain_content = content_result["plain_content"]
                        elif error:
                            logger.warning(f"Using fallback content for article: {title[:50]}... (error: {error})")
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

                    # Add delay between article fetches to avoid WeChat rate limiting
                    await asyncio.sleep(8)

                account.last_checked_at = datetime.now(timezone.utc)
                account.last_success_at = datetime.now(timezone.utc)
                await session.commit()

            except Exception as e:
                logger.error(f"Failed to fetch articles for {account.account_name}: {e}")
                errors.append(f"{account.account_name}: {e}")
                account.last_checked_at = datetime.now(timezone.utc)
                await session.commit()

        # Determine status based on actual results
        if errors:
            status = "failed"
        elif total_fetched == 0:
            status = "failed"
            errors.append("No articles fetched from any source. Check WeChat login status and source accounts.")
        else:
            status = "completed"

        return {
            "workflow_id": workflow_id,
            "status": status,
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
    """Classify pending articles using LLM.
    
    Each article is processed independently with its own session to avoid
    concurrency issues and ensure data consistency.
    """
    BATCH_SIZE = 10
    MAX_WORKFLOW_MINUTES = 30
    MAX_ITERATIONS = 100  # Prevent infinite loops
    total_classified = 0
    total_errors = []
    start_time = datetime.now(timezone.utc)
    iteration = 0
    
    # Get provider info (separate session)
    provider = None
    async with async_session() as session:
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
        logger.warning("No enabled LLM provider found for classification")
        return {
            "workflow_id": workflow_id,
            "classified_count": 0,
            "message": "No enabled LLM provider found",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    
    logger.info(f"Starting article classification with provider: {provider.name}, model: {provider.default_model}")

    while iteration < MAX_ITERATIONS:
        iteration += 1
        
        # Check overall workflow timeout
        elapsed = datetime.now(timezone.utc) - start_time
        if elapsed.total_seconds() > MAX_WORKFLOW_MINUTES * 60:
            total_errors.append(f"Workflow timed out after {MAX_WORKFLOW_MINUTES} minutes")
            logger.warning(f"Workflow timeout reached after {elapsed.total_seconds()}s")
            break
        
        # Fetch batch of new articles (fresh session each time)
        articles = []
        async with async_session() as session:
            result = await session.execute(
                select(RawArticle).where(
                    RawArticle.status == "new",
                ).order_by(RawArticle.created_at.asc()).limit(BATCH_SIZE)
            )
            articles = result.scalars().all()
        
        if not articles:
            logger.info("No more new articles to classify")
            break
        
        logger.info(f"Processing batch {iteration}: {len(articles)} articles")

        # Process articles concurrently with limited concurrency
        batch_classified = 0
        batch_errors = []

        semaphore = asyncio.Semaphore(3)

        async def process_with_semaphore(article: RawArticle) -> tuple[bool, str | None]:
            async with semaphore:
                # Check timeout before processing each article
                elapsed = datetime.now(timezone.utc) - start_time
                if elapsed.total_seconds() > MAX_WORKFLOW_MINUTES * 60:
                    return False, "Workflow timed out"
                return await _classify_single_article(article, provider)

        results = await asyncio.gather(
            *[process_with_semaphore(a) for a in articles],
            return_exceptions=True,
        )

        for result in results:
            if isinstance(result, Exception):
                error_msg = f"Unexpected error: {result}"
                batch_errors.append(error_msg)
                total_errors.append(error_msg)
                logger.warning(error_msg)
            else:
                success, error = result
                if success:
                    batch_classified += 1
                    total_classified += 1
                else:
                    batch_errors.append(error)
                    total_errors.append(error)
                    logger.warning(f"Failed to classify article: {error}")
        
        logger.info(f"Batch {iteration} complete: {batch_classified}/{len(articles)} classified, {len(batch_errors)} errors")
    
    if iteration >= MAX_ITERATIONS:
        logger.warning(f"Reached maximum iterations ({MAX_ITERATIONS})")
        total_errors.append(f"Reached maximum iterations ({MAX_ITERATIONS})")

    # Determine status based on results
    if total_errors and total_classified == 0:
        status = "failed"
    elif total_errors:
        status = "partial"
    else:
        status = "completed"
    
    elapsed_total = datetime.now(timezone.utc) - start_time
    logger.info(f"Classification complete: {total_classified} articles, {len(total_errors)} errors, status={status}, duration={elapsed_total.total_seconds():.1f}s")

    return {
        "workflow_id": workflow_id,
        "status": status,
        "classified_count": total_classified,
        "total_errors": len(total_errors),
        "errors": total_errors[:10],
        "duration_seconds": elapsed_total.total_seconds(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


async def _classify_single_article(article: RawArticle, provider: LlmProvider) -> tuple[bool, str | None]:
    """Classify a single article with its own session.
    
    Returns: (success: bool, error_message: str | None)
    """
    article_id = article.id
    article_title = article.title[:50] if article.title else "Unknown"
    
    try:
        # Call LLM for classification
        classification = await asyncio.wait_for(
            _classify_article_async(article, provider),
            timeout=120,
        )
        
        # Update article in a fresh session
        async with async_session() as session:
            # Re-fetch article to ensure we have latest state
            result = await session.execute(
                select(RawArticle).where(RawArticle.id == article_id)
            )
            db_article = result.scalar_one_or_none()
            
            if not db_article:
                return False, f"Article {article_id[:8]} not found in database"
            
            # Update fields
            db_article.is_relevant = classification.get("is_relevant")
            db_article.relevance_score = classification.get("relevance_score")
            db_article.primary_event_type = classification.get("event_type")
            db_article.tags_json = classification.get("tags", [])
            db_article.companies_json = classification.get("companies", [])
            db_article.summary_short = classification.get("summary_short", "")
            db_article.summary_long = classification.get("summary_long", "")
            db_article.status = "classified"
            db_article.updated_at = datetime.now(timezone.utc)
            
            if provider:
                db_article.llm_provider_id = provider.id
                db_article.llm_model = provider.default_model

            try:
                await event_service.sync_article_events(session, db_article, classification)
            except Exception as e:
                logger.warning(f"Failed to sync aggregated events for {article_id[:8]}: {e}")
                # Don't fail the whole classification if event aggregation fails

            await session.commit()
            logger.debug(f"Successfully classified article: {article_title}")
            return True, None
            
    except asyncio.TimeoutError:
        error_msg = f"LLM request timed out (120s) for: {article_title}"
        logger.warning(error_msg)
        return False, error_msg
    except Exception as e:
        error_msg = f"{article_title}: {e}"
        logger.exception(f"Error classifying article {article_id[:8]}")
        return False, error_msg


async def _classify_article_async(article, provider) -> dict:
    """Classify a single article using LLM (async)."""
    import json
    import httpx
    from app.core.security import decrypt_api_key
    from app.core.prompt_loader import load_prompt

    if not provider:
        return {
            "is_relevant": None,
            "relevance_score": 0,
            "event_type": None,
            "events": [],
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

    prompt_cfg = load_prompt("classify")
    user_prompt = prompt_cfg["user_prompt_template"].format(
        title=article.title,
        account_name=article.account_name,
        content=content_for_llm,
        relevance_criteria=prompt_cfg.get("relevance_criteria", ""),
    )
    system_prompt = prompt_cfg.get("system_prompt", "")
    max_tokens = prompt_cfg.get("max_tokens", 1500)
    temperature = prompt_cfg.get("temperature", 0.1)

    payload = {
        "model": provider.default_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }

    def _try_repair_json(text: str) -> str:
        """尝试修复常见的JSON格式问题。"""
        import re
        # 移除 markdown 代码块
        text = re.sub(r'^```(?:json)?\s*', '', text)
        text = re.sub(r'\s*```\s*$', '', text)
        text = text.strip()
        # 移除行尾注释（// 开头的注释）
        text = re.sub(r'//.*$', '', text, flags=re.MULTILINE)
        # 修复尾部多余的逗号
        text = re.sub(r',\s*}', '}', text)
        text = re.sub(r',\s*]', ']', text)
        return text

    for attempt in range(provider.max_retries):
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                content_str = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                
                # Extract JSON from response
                content_str = _try_repair_json(content_str)
                
                result = json.loads(content_str)
                events = result.get("events", []) if isinstance(result.get("events"), list) else []
                primary_event_type = result.get("event_type")
                companies = result.get("companies", [])[:10]
                if events and not primary_event_type:
                    primary_event_type = events[0].get("event_type")
                if events and not companies:
                    collected = []
                    for event in events:
                        participants = event.get("participants") or event.get("companies") or []
                        for participant in participants:
                            if isinstance(participant, str):
                                collected.append(participant)
                            elif isinstance(participant, dict) and participant.get("name"):
                                collected.append(participant["name"])
                    companies = collected[:10]
                return {
                    "is_relevant": result.get("is_relevant"),
                    "relevance_score": result.get("relevance_score", 0),
                    "event_type": primary_event_type,
                    "events": events[:5],
                    "tags": result.get("tags", [])[:5],
                    "companies": companies,
                    "summary_short": result.get("summary_short", ""),
                    "summary_long": result.get("summary_long", ""),
                }
        except json.JSONDecodeError as e:
            logger.warning(f"LLM JSON parse error (attempt {attempt+1}/{provider.max_retries}): {e}")
            if attempt == provider.max_retries - 1:
                logger.error(f"LLM classification failed after {provider.max_retries} attempts")
                return {
                    "is_relevant": None,
                    "relevance_score": 0,
                    "event_type": None,
                    "events": [],
                    "tags": [],
                    "companies": [],
                    "summary_short": article.plain_content[:200] if article.plain_content else "",
                    "summary_long": "",
                }
            import asyncio
            await asyncio.sleep(2 ** attempt)
        except Exception as e:
            if attempt == provider.max_retries - 1:
                logger.error(f"LLM classification failed: {e}")
                return {
                    "is_relevant": None,
                    "relevance_score": 0,
                    "event_type": None,
                    "events": [],
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
        "events": [],
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
                    plain_content = rss_content or entry.get("title", "")  # fallback to title
                    html_content = None
                    if link:
                        content_result = await _fetch_rss_article_content(link)
                        error = content_result.get("error")
                        if content_result.get("plain_content"):
                            plain_content = content_result["plain_content"]
                        elif error:
                            logger.warning(f"Using fallback content for RSS article: {entry.get('title', '')[:50]}... (error: {error})")
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

        # Determine status based on actual results
        if errors:
            status = "failed"
        elif total_fetched == 0:
            status = "failed"
            errors.append("No articles fetched from any RSS feed. Check feed URLs and connectivity.")
        else:
            status = "completed"

        return {
            "workflow_id": workflow_id,
            "status": status,
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


def _sanitize_digest_content(text: str) -> str:
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", text)
    text = re.sub(r"https?://[^\s)>]+", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


_DIGEST_THEME_TAG_RE = re.compile(r"<!--\s*events:\s*([a-zA-Z0-9,\-\s]+)\s*-->")


def _digest_category_name(event: dict) -> str:
    return event.get("event_type") or "其他"


def _group_digest_events_by_category(events: list[dict]) -> list[dict]:
    grouped: dict[str, dict] = {}
    for event_index, event in enumerate(events):
        category = _digest_category_name(event)
        entry = grouped.setdefault(
            category,
            {
                "name": category,
                "events": [],
            },
        )
        entry["events"].append({**event, "_digest_event_index": event_index})
    return list(grouped.values())


def _digest_publish_time_sort_value(value) -> float:
    dt = _ensure_tz(value)
    if dt is None:
        return 0.0
    return dt.timestamp()


def _render_digest_category_links(category: dict) -> list[str]:
    candidates: list[dict] = []
    for event in category["events"]:
        for article in (event.get("representative_articles") or [])[:3]:
            title = article.get("title")
            url = article.get("article_url")
            if not title or not url:
                continue
            candidates.append(
                {
                    "title": title,
                    "url": url,
                    "source": article.get("account_name") or "未知来源",
                    "importance": event.get("importance") or 0,
                    "publish_sort": _digest_publish_time_sort_value(article.get("publish_time")),
                    "event_index": event.get("_digest_event_index", 0),
                }
            )

    candidates.sort(
        key=lambda item: (
            -(item["importance"] or 0),
            -item["publish_sort"],
            item["event_index"],
        )
    )

    rendered: list[str] = []
    seen_urls: set[str] = set()
    for item in candidates:
        if item["url"] in seen_urls:
            continue
        seen_urls.add(item["url"])
        rendered.append(f"- [{item['title']}]({item['url']}) — {item['source']}")
    return rendered


def _fallback_category_summary(category: dict) -> str:
    item_count = len(category["events"])
    if item_count <= 0:
        return "本分类暂无可展示内容。"
    if item_count == 1:
        return "本分类聚焦 1 个重点事件，下列链接可用于查看完整上下文。"
    return f"本分类共整理 {item_count} 个相关事件，下面汇总代表文章链接供进一步查看。"


def _build_digest_theme_pool(events: list[dict]) -> dict[str, dict]:
    theme_pool: dict[str, dict] = {}
    for event_index, event in enumerate(events):
        event_id = event.get("id")
        if not event_id:
            continue
        theme_pool[event_id] = {
            **event,
            "_digest_event_index": event_index,
        }
    return theme_pool


def _render_digest_theme_links(theme_events: list[dict]) -> list[str]:
    candidates: list[dict] = []
    for event in theme_events:
        for article in (event.get("representative_articles") or [])[:3]:
            title = article.get("title")
            url = article.get("article_url")
            if not title or not url:
                continue
            candidates.append(
                {
                    "title": title,
                    "url": url,
                    "source": article.get("account_name") or "未知来源",
                    "importance": event.get("importance") or 0,
                    "publish_sort": _digest_publish_time_sort_value(article.get("publish_time")),
                    "event_index": event.get("_digest_event_index", 0),
                }
            )

    candidates.sort(
        key=lambda item: (
            -(item["importance"] or 0),
            -item["publish_sort"],
            item["event_index"],
        )
    )

    rendered: list[str] = []
    seen_urls: set[str] = set()
    for item in candidates:
        if item["url"] in seen_urls:
            continue
        seen_urls.add(item["url"])
        rendered.append(f"- [{item['title']}]({item['url']}) — {item['source']}")
    return rendered


def _fallback_theme_summary(theme_events: list[dict]) -> str:
    item_count = len(theme_events)
    if item_count <= 0:
        return "暂无可展示内容。"
    if item_count == 1:
        return "这里补充 1 个未被主题归纳的重点事件，附上相关文章供进一步查看。"
    return f"这里补充 {item_count} 个未被主题归纳的重点事件，附上相关文章供进一步查看。"


def _parse_digest_theme_sections(content: str) -> tuple[list[str], list[dict]]:
    lines = content.splitlines()
    intro_lines: list[str] = []
    sections: list[dict] = []
    current_section: dict | None = None

    def flush_current():
        nonlocal current_section
        if current_section is None:
            return
        body = "\n".join(current_section["lines"]).strip()
        raw_event_ids = current_section.pop("raw_event_ids", [])
        event_ids: list[str] = []
        seen_ids: set[str] = set()
        for event_id in raw_event_ids:
            if event_id and event_id not in seen_ids:
                seen_ids.add(event_id)
                event_ids.append(event_id)
        sections.append(
            {
                "title": current_section["title"],
                "body": body,
                "event_ids": event_ids,
            }
        )
        current_section = None

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## "):
            flush_current()
            current_section = {
                "title": stripped[3:].strip(),
                "lines": [],
                "raw_event_ids": [],
            }
            continue

        matches = _DIGEST_THEME_TAG_RE.findall(line)
        if matches:
            if current_section is not None:
                for match in matches:
                    current_section["raw_event_ids"].extend([part.strip() for part in match.split(",") if part.strip()])
            continue

        if current_section is None:
            intro_lines.append(line)
        else:
            current_section["lines"].append(line)

    flush_current()
    intro = "\n".join(intro_lines).strip()
    return ([intro] if intro else []), sections


def _inject_digest_theme_links(content: str, events: list[dict]) -> str:
    intro_parts, sections = _parse_digest_theme_sections(content)
    theme_pool = _build_digest_theme_pool(events)
    assigned_event_ids: set[str] = set()
    output: list[str] = [part for part in intro_parts if part]

    for section in sections:
        theme_events: list[dict] = []
        for event_id in section["event_ids"]:
            event = theme_pool.get(event_id)
            if not event:
                continue
            theme_events.append(event)
            assigned_event_ids.add(event_id)

        if output and output[-1].strip():
            output.append("")
        output.append(f"## {section['title']}")
        output.append("")
        if section["body"]:
            output.append(section["body"])
        links = _render_digest_theme_links(theme_events)
        if links:
            output.append("")
            output.extend(links)
        output.append("")

    missing_events = [event for event_id, event in theme_pool.items() if event_id not in assigned_event_ids]
    if missing_events:
        if output and output[-1].strip():
            output.append("")
        output.append("## 其他重点动态")
        output.append("")
        output.append(_fallback_theme_summary(missing_events))
        links = _render_digest_theme_links(missing_events)
        if links:
            output.append("")
            output.extend(links)
        output.append("")

    return "\n".join(output).strip()


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


def _generate_digest_content(events, provider) -> str:
    from app.core.prompt_loader import load_prompt

    if not events:
        return "# 每日摘要\n\n今日暂无事件。"

    beijing_tz = timezone(timedelta(hours=8))
    header = f"# 每日摘要\n\n**日期**: {datetime.now(beijing_tz).strftime('%Y-%m-%d')}\n\n"
    header += f"**共 {len(events)} 个事件**\n\n---\n\n"

    if provider:
        try:
            selected_articles = event_service.select_digest_articles(events, max_articles=30)
            event_summaries = []
            event_theme_pool = _build_digest_theme_pool(events)
            for index, event in enumerate(events, 1):
                participants = "、".join(entity["name"] for entity in event.get("entities", [])[:4]) or "未识别主体"
                event_summary = (event.get("summary_long") or event.get("summary_short") or "暂无摘要").strip()
                latest_article_time = event.get("selection_latest_article_time") or event.get("latest_article_time")
                representative_titles = "；".join(
                    article["title"]
                    for article in event.get("representative_articles", [])[:3]
                    if article.get("title")
                ) or "无"
                event_summaries.append(
                    f"{index}. 事件ID: {event['id']}\n"
                    f"   - 标题: {event['title']}\n"
                    f"   - 当前事件分类: {_digest_category_name(event)}\n"
                    f"   - 参与方: {participants}\n"
                    f"   - 事件摘要: {event_summary[:320]}\n"
                    f"   - 最新相关文章时间: {latest_article_time.isoformat() if latest_article_time else '未知'}\n"
                    f"   - 关联文章数: {event.get('article_count', 0)}\n"
                    f"   - 代表文章标题: {representative_titles}"
                )

            article_summaries = []
            for i, article in enumerate(selected_articles, 1):
                event_id = article.get("event_id")
                event = event_theme_pool.get(event_id, {})
                article_summaries.append(
                    f"{i}. [事件ID: {event_id}] {article['title']}\n"
                    f"   - 当前事件分类: {_digest_category_name(event)}\n"
                    f"   - 所属事件: {article['event_title']}\n"
                    f"   - 来源: {article['account_name']}\n"
                    f"   - 发布时间: {article['publish_time'].isoformat() if article.get('publish_time') else '未知'}\n"
                    f"   - 内容摘要: {article['content_text']}"
                )

            prompt_cfg = load_prompt("digest")
            events_text = "\n\n".join(event_summaries)
            articles_text = "\n\n".join(article_summaries) if article_summaries else "无额外文章材料。"
            user_prompt = prompt_cfg["user_prompt_template"].format(
                event_count=len(events),
                article_count=len(selected_articles),
                focus_area=prompt_cfg.get("focus_area", "科技领域"),
                events=events_text,
                articles=articles_text,
            )
            system_prompt = prompt_cfg.get("system_prompt", "")
            timeout = prompt_cfg.get("timeout", 120)

            result = _call_llm_sync(
                provider=provider,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                timeout=timeout,
            )

            if result.get("success"):
                raw = result["content"]
                content = _sanitize_digest_content(raw)
                content = _fix_markdown_headings(content)
                content = _inject_digest_theme_links(content, events)
                content = header + content
                footer = f"\n\n---\n\n*摘要由 AI 自动生成，使用模型: {provider.default_model}*"
                return content + footer
            else:
                logger.warning(f"LLM call failed: {result.get('error')}")
        except Exception as e:
            logger.warning(f"LLM digest generation failed, falling back to simple format: {e}")

    content = header
    by_type = {}
    for event in events:
        by_type.setdefault(event.get("event_type") or "其他", []).append(event)

    content += "## 📊 今日概览\n\n"
    content += f"共识别 **{len(events)}** 个聚合事件。\n\n"

    for event_type, items in by_type.items():
        content += f"## {event_type}\n\n"
        category = {"name": event_type, "events": [{**event, "_digest_event_index": index} for index, event in enumerate(items)]}
        content += _fallback_category_summary(category) + "\n\n"
        links = _render_digest_category_links(category)
        if links:
            content += "\n".join(links) + "\n"
        content += "\n"

    return content


async def do_generate_digest(workflow_id: str) -> dict:
    session = async_session()
    try:
        # Use Beijing time (Asia/Shanghai, UTC+8) for digest date calculation
        beijing_tz = timezone(timedelta(hours=8))
        now_beijing = datetime.now(beijing_tz)
        digest_date = now_beijing.replace(hour=0, minute=0, second=0, microsecond=0)

        events = await event_service.get_digest_candidate_events(
            session,
            now=now_beijing,
            fallback_limit=30,
        )

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

        content_md = _generate_digest_content(events, digest_provider)

        result = await session.execute(
            select(DailyDigest).where(DailyDigest.digest_date == digest_date)
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.content_markdown = content_md
            existing.item_count = len(events)
            existing.status = "published"
            existing.generated_at = datetime.now(timezone.utc)
            if digest_provider:
                existing.llm_provider_id = digest_provider.id
                existing.llm_model = digest_provider.default_model
            digest = existing
        else:
            digest = DailyDigest(
                id=str(uuid.uuid4()),
                digest_date=digest_date,
                content_markdown=content_md,
                item_count=len(events),
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
            "digest_date": digest_date.strftime("%Y-%m-%d"),
            "item_count": len(events),
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
