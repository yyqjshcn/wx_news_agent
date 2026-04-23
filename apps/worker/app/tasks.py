from datetime import datetime, timedelta, timezone
import logging
import re

from app.core.security import decrypt_api_key
from app.db import get_session
from app.models import (
    WorkflowRunStatus,
    get_workflow,
    get_workflow_run,
    LlmProvider,
    Event,
    EventEntity,
    ArticleEvent,
    RawArticle,
)
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
            _do_generate_digest,
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


_MIN_DATETIME_UTC = datetime.min.replace(tzinfo=timezone.utc)
_DIGEST_EVENT_SUMMARY_LIMIT = 320
_DIGEST_ARTICLE_CONTENT_LIMIT = 480


def _coerce_datetime(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    return None


def _clip_text(text: str | None, limit: int) -> str:
    if not text:
        return ""
    value = text.strip()
    if len(value) <= limit:
        return value
    return value[: max(limit - 1, 0)].rstrip() + "…"


def _article_datetime(article: RawArticle):
    return _coerce_datetime(article.publish_time or article.created_at)


def _matches_window(dt, *, window_start, window_end, window_end_inclusive=True):
    dt = _coerce_datetime(dt)
    if dt is None or window_start is None or window_end is None:
        return False
    if dt < window_start:
        return False
    if window_end_inclusive:
        return dt <= window_end
    return dt < window_end


def _build_digest_article_payload(article: RawArticle, *, event_id: str, event_title: str, window_start=None, window_end=None, window_end_inclusive=True):
    published_at = _article_datetime(article)
    summary_long = (article.summary_long or "").strip()
    summary_short = (article.summary_short or "").strip()
    content_text = summary_long or summary_short or (article.title or "").strip()
    return {
        "id": article.id,
        "event_id": event_id,
        "event_title": event_title,
        "title": article.title,
        "article_url": article.article_url,
        "account_name": article.account_name,
        "publish_time": published_at,
        "summary_long": summary_long,
        "summary_short": summary_short,
        "content_text": _clip_text(content_text, _DIGEST_ARTICLE_CONTENT_LIMIT),
        "has_summary_long": bool(summary_long),
        "is_relevant": bool(article.is_relevant),
        "relevance_score": float(article.relevance_score or 0),
        "in_window": _matches_window(
            published_at,
            window_start=window_start,
            window_end=window_end,
            window_end_inclusive=window_end_inclusive,
        ),
    }


def _digest_article_sort_key(article: dict):
    published_at = _coerce_datetime(article.get("publish_time")) or _MIN_DATETIME_UTC
    return (
        1 if article.get("in_window") else 0,
        1 if article.get("is_relevant") else 0,
        1 if article.get("has_summary_long") else 0,
        published_at,
        float(article.get("relevance_score") or 0),
    )


def _select_digest_articles(events: list[dict], max_articles: int = 30) -> list[dict]:
    ranked_by_event = []
    selected_ids = set()
    selected = []

    for event_index, event in enumerate(events):
        digest_articles = event.get("digest_articles") or []
        ranked = sorted(digest_articles, key=_digest_article_sort_key, reverse=True)
        relevant_ranked = [article for article in ranked if article.get("is_relevant")]
        if relevant_ranked:
            ranked = relevant_ranked + [article for article in ranked if not article.get("is_relevant")]
        ranked_by_event.append((event_index, event["id"], event["title"], ranked))

    for _, event_id, event_title, ranked in ranked_by_event:
        if len(selected) >= max_articles:
            break
        if not ranked:
            continue
        top_article = ranked[0]
        if top_article["id"] in selected_ids:
            continue
        selected_ids.add(top_article["id"])
        selected.append({**top_article, "event_id": event_id, "event_title": event_title})

    remaining = []
    for event_index, event_id, event_title, ranked in ranked_by_event:
        for article in ranked:
            if article["id"] in selected_ids:
                continue
            remaining.append((event_index, {**article, "event_id": event_id, "event_title": event_title}))

    remaining.sort(key=lambda item: _digest_article_sort_key(item[1]), reverse=True)
    for _, article in remaining:
        if len(selected) >= max_articles:
            break
        if article["id"] in selected_ids:
            continue
        selected_ids.add(article["id"])
        selected.append(article)

    return selected


def _select_recent_relevant_events(session, *, window_start, window_end, window_end_inclusive):
    from sqlalchemy import select

    publish_filters = [
        RawArticle.publish_time.is_not(None),
        RawArticle.publish_time >= window_start,
    ]
    if window_end_inclusive:
        publish_filters.append(RawArticle.publish_time <= window_end)
    else:
        publish_filters.append(RawArticle.publish_time < window_end)

    rows = session.execute(
        select(Event, RawArticle)
        .join(ArticleEvent, ArticleEvent.event_id == Event.id)
        .join(RawArticle, RawArticle.id == ArticleEvent.article_id)
        .where(
            Event.status == "active",
            RawArticle.is_relevant == True,
            *publish_filters,
        )
        .order_by(RawArticle.publish_time.desc(), Event.importance.desc(), Event.updated_at.desc())
    ).all()

    grouped = {}
    for event, article in rows:
        article_time = _article_datetime(article)
        if article_time is None:
            continue
        entry = grouped.setdefault(
            event.id,
            {"event": event, "latest_article_time": article_time},
        )
        if article_time > entry["latest_article_time"]:
            entry["latest_article_time"] = article_time

    ordered = sorted(
        grouped.values(),
        key=lambda item: (
            item["latest_article_time"],
            item["event"].importance or 0,
            _coerce_datetime(item["event"].updated_at) or _MIN_DATETIME_UTC,
        ),
        reverse=True,
    )
    return [item["event"] for item in ordered], {
        item["event"].id: item["latest_article_time"] for item in ordered
    }


def _select_fallback_digest_events(session, *, limit: int):
    from sqlalchemy import func, select

    return session.execute(
        select(Event)
        .where(Event.status == "active")
        .order_by(
            Event.included_in_digest.desc(),
            Event.importance.desc(),
            func.coalesce(Event.event_date_end, Event.updated_at).desc(),
        )
        .limit(limit)
    ).scalars().all()


def _serialize_digest_events(session, events: list[Event], *, window_start=None, window_end=None, window_end_inclusive=True, latest_matching_article_time=None) -> list[dict]:
    from sqlalchemy import select

    serialized = []
    latest_matching_article_time = latest_matching_article_time or {}
    for event in events:
        entities = session.execute(
            select(EventEntity).where(EventEntity.event_id == event.id).order_by(EventEntity.created_at.asc())
        ).scalars().all()
        articles = [
            row[1]
            for row in session.execute(
                select(ArticleEvent, RawArticle)
                .join(RawArticle, RawArticle.id == ArticleEvent.article_id)
                .where(ArticleEvent.event_id == event.id)
                .order_by(RawArticle.publish_time.desc(), RawArticle.created_at.desc())
            ).all()
        ]
        serialized.append(
            {
                "id": event.id,
                "title": event.title,
                "event_type": event.event_type,
                "summary_short": event.summary_short,
                "summary_long": event.summary_long,
                "importance": event.importance,
                "article_count": len(articles),
                "latest_article_time": max([_article_datetime(article) or _MIN_DATETIME_UTC for article in articles], default=None),
                "selection_latest_article_time": latest_matching_article_time.get(event.id),
                "entities": [{"name": entity.name} for entity in entities],
                "representative_articles": [
                    {
                        "title": article.title,
                        "article_url": article.article_url,
                        "account_name": article.account_name,
                    }
                    for article in articles[:3]
                ],
                "related_articles": [
                    {
                        "title": article.title,
                        "article_url": article.article_url,
                        "account_name": article.account_name,
                    }
                    for article in articles
                ],
                "digest_articles": [
                    _build_digest_article_payload(
                        article,
                        event_id=event.id,
                        event_title=event.title,
                        window_start=window_start,
                        window_end=window_end,
                        window_end_inclusive=window_end_inclusive,
                    )
                    for article in articles
                ],
            }
        )
    return serialized


def _get_digest_candidate_events(session, now=None, fallback_limit: int = 30) -> list[dict]:
    now = _coerce_datetime(now) or datetime.now(timezone.utc)
    window_24h = now - timedelta(hours=24)
    window_48h = now - timedelta(hours=48)

    recent_events, recent_latest = _select_recent_relevant_events(
        session,
        window_start=window_24h,
        window_end=now,
        window_end_inclusive=True,
    )
    if recent_events:
        return _serialize_digest_events(
            session,
            recent_events,
            window_start=window_24h,
            window_end=now,
            window_end_inclusive=True,
            latest_matching_article_time=recent_latest,
        )

    older_events, older_latest = _select_recent_relevant_events(
        session,
        window_start=window_48h,
        window_end=window_24h,
        window_end_inclusive=False,
    )
    if older_events:
        return _serialize_digest_events(
            session,
            older_events,
            window_start=window_48h,
            window_end=window_24h,
            window_end_inclusive=False,
            latest_matching_article_time=older_latest,
        )

    fallback_events = _select_fallback_digest_events(session, limit=fallback_limit)
    if not fallback_events:
        return []
    return _serialize_digest_events(session, fallback_events)


def _do_generate_digest(workflow_id: str) -> dict:
    from app.db import get_session
    from app.models import DailyDigest, LlmProvider
    from sqlalchemy import select

    with get_session() as session:
        beijing_tz = timezone(timedelta(hours=8))
        now_beijing = datetime.now(beijing_tz)
        today = now_beijing.replace(hour=0, minute=0, second=0, microsecond=0)

        events = _get_digest_candidate_events(session, now=now_beijing, fallback_limit=30)

        digest_provider = session.execute(
            select(LlmProvider).where(
                LlmProvider.enabled == True,
                LlmProvider.is_default_for_digest == True,
            )
        ).scalar_one_or_none()

        if not digest_provider:
            digest_provider = session.execute(
                select(LlmProvider).where(
                    LlmProvider.enabled == True,
                )
            ).scalar_one_or_none()

        content_md = _generate_digest_content(events, digest_provider, session)

        existing = session.execute(
            select(DailyDigest).where(DailyDigest.digest_date == today)
        ).scalar_one_or_none()

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
                id=str(__import__("uuid").uuid4()),
                digest_date=today,
                content_markdown=content_md,
                item_count=len(events),
                status="published",
                generated_at=datetime.now(timezone.utc),
            )
            if digest_provider:
                digest.llm_provider_id = digest_provider.id
                digest.llm_model = digest_provider.default_model
            session.add(digest)

        session.commit()

        return {
            "workflow_id": workflow_id,
            "digest_date": today.strftime("%Y-%m-%d"),
            "item_count": len(events),
            "digest_id": digest.id,
            "used_llm": digest_provider is not None,
            "llm_provider": digest_provider.name if digest_provider else None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


def _generate_digest_content(events: list[Event], provider: LlmProvider | None, session) -> str:
    if not events:
        return "# 每日摘要\n\n今日暂无事件。"

    serialized_events = events

    beijing_tz = timezone(timedelta(hours=8))
    header = f"# 每日摘要\n\n**日期**: {datetime.now(beijing_tz).strftime('%Y-%m-%d')}\n\n"
    header += f"**共 {len(serialized_events)} 个事件**\n\n---\n\n"

    if provider:
        try:
            selected_articles = _select_digest_articles(serialized_events, max_articles=30)
            event_summaries = []
            event_theme_pool = _build_digest_theme_pool(serialized_events)
            for index, event in enumerate(serialized_events, 1):
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
                    f"   - 事件摘要: {event_summary[:_DIGEST_EVENT_SUMMARY_LIMIT]}\n"
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

            prompt = (
                f"以下是本次摘要涉及的 {len(serialized_events)} 个候选事件，以及从中挑选出的 {len(selected_articles)} 篇补充文章材料。\n"
                "请生成一份简洁的每日摘要，包含：\n"
                "1. 一段话概述今日整体动态（3-5句话）\n"
                "2. 基于全部事件，自主归纳 3-6 个主题，每个主题使用 `## 主题标题`\n"
                "3. 主题标题风格参考“具身智能商业化加速”“融资升温，头部格局快速形成”这类编辑部式标题\n"
                "4. 每个主题下只写 3-5 句话总述，不要输出事件标题、小标题、编号、列表或链接\n"
                "5. 每个主题块末尾必须单独追加一行 `<!-- events: 事件ID1,事件ID2 -->`，列出该主题对应的全部事件ID\n"
                "6. 所有事件ID必须来自输入素材，且全部事件都必须至少被一个主题覆盖\n"
                "7. 使用标准 Markdown 格式，中文\n\n"
                "注意：\n"
                "- 每个 `## ` 标题前后必须各空一行\n"
                "- 主题标题不需要复述原始事件分类，可以自由归纳\n"
                "- 不要输出 Markdown 链接、裸 URL 或 HTML 链接\n"
                "- 补充文章材料只是帮助理解细节，不能替代主题覆盖\n"
                "- 不要使用 HTML 标签\n\n"
                f"事件素材：\n\n" + "\n\n".join(event_summaries) + "\n\n"
                f"补充文章材料：\n\n" + ("\n\n".join(article_summaries) if article_summaries else "无额外文章材料。")
            )

            result = _call_llm_sync(
                provider=provider,
                system_prompt="你是科技新闻编辑助手，擅长从文章中提炼关键趋势，生成简洁的每日摘要。",
                user_prompt=prompt,
                timeout=120,
            )

            if result.get("success"):
                raw = result["content"]
                content = _sanitize_digest_content(raw)
                content = _fix_markdown_headings(content)
                content = _inject_digest_theme_links(content, serialized_events)
                content = header + content
                footer = f"\n\n---\n\n*摘要由 AI 自动生成，使用模型: {provider.default_model}*"
                return content + footer
            else:
                logger.warning(f"LLM call failed: {result.get('error')}")
        except Exception as e:
            logger.warning(f"LLM digest generation failed, falling back to simple format: {e}")

    content = header
    by_type: dict[str, list] = {}
    for event in serialized_events:
        by_type.setdefault(event.get("event_type") or "其他", []).append(event)

    content += "## 📊 今日概览\n\n"
    content += f"共整理 **{len(serialized_events)}** 个聚合事件。\n\n"

    for event_type, items in by_type.items():
        content += f"## {event_type}\n\n"
        category = {"name": event_type, "events": [{**event, "_digest_event_index": index} for index, event in enumerate(items)]}
        content += _fallback_category_summary(category) + "\n\n"
        links = _render_digest_category_links(category)
        if links:
            content += "\n".join(links) + "\n"
        content += "\n"

    return content


def _fix_markdown_headings(text: str) -> str:
    """Ensure ## headings have proper newlines before and after."""
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
    grouped = {}
    for event_index, event in enumerate(events):
        category = _digest_category_name(event)
        entry = grouped.setdefault(category, {"name": category, "events": []})
        entry["events"].append({**event, "_digest_event_index": event_index})
    return list(grouped.values())


def _digest_publish_time_sort_value(value) -> float:
    dt = _coerce_datetime(value)
    if dt is None:
        return 0.0
    return dt.timestamp()


def _render_digest_category_links(category: dict) -> list[str]:
    candidates = []
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

    rendered = []
    seen_urls = set()
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


_SECTION_CATEGORIES = (
    ("embodied_data", ("数据集", "训练数据", "数据采集", "数据云", "数据标注", "数据基础设施")),
    ("world_model", ("世界模型", "world model", "空间理解")),
    ("embodied_other", ("人形机器人", "具身机器人", "具身智能", "embodied", "具身AI", "机器人")),
)


def _classify_digest_section(section: dict, theme_pool: dict) -> str:
    text = (section.get("title") or "").lower()

    for category, keywords in _SECTION_CATEGORIES:
        for keyword in keywords:
            if keyword.lower() in text:
                return category

    body_text = (section.get("body") or "").lower()
    data_kw = (
        "数据集", "训练数据", "数据采集", "数据基础设施", "数据编译", "数据范式",
        "数据质量", "训练范式", "仿真数据", "embodied dataset", "data collection",
    )
    for keyword in data_kw:
        if keyword.lower() in body_text:
            return "embodied_data"

    wm_kw = ("世界模型", "world model", "空间理解")
    for keyword in wm_kw:
        if keyword.lower() in body_text:
            return "world_model"

    return "other"


_SECTION_CATEGORY_ORDER = {
    "embodied_data": 0,
    "world_model": 1,
    "embodied_other": 2,
    "other": 3,
}


def _sort_digest_sections(sections: list[dict], theme_pool: dict) -> list[dict]:
    def section_key(section):
        category = _classify_digest_section(section, theme_pool)
        return _SECTION_CATEGORY_ORDER.get(category, 3)

    return sorted(sections, key=section_key)


def _build_digest_theme_pool(events: list[dict]) -> dict[str, dict]:
    theme_pool = {}
    for event_index, event in enumerate(events):
        event_id = event.get("id")
        if not event_id:
            continue
        theme_pool[event_id] = {**event, "_digest_event_index": event_index}
    return theme_pool


def _render_digest_theme_links(theme_events: list[dict]) -> list[str]:
    candidates = []
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

    rendered = []
    seen_urls = set()
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


def _parse_digest_theme_sections(content: str):
    lines = content.splitlines()
    intro_lines = []
    sections = []
    current_section = None

    def flush_current():
        nonlocal current_section
        if current_section is None:
            return
        body = "\n".join(current_section["lines"]).strip()
        raw_event_ids = current_section.pop("raw_event_ids", [])
        event_ids = []
        seen_ids = set()
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
            current_section = {"title": stripped[3:].strip(), "lines": [], "raw_event_ids": []}
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
    sections = _sort_digest_sections(sections, theme_pool)
    assigned_event_ids = set()
    output = [part for part in intro_parts if part]

    for section in sections:
        theme_events = []
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


def _call_llm_sync(provider: LlmProvider, system_prompt: str, user_prompt: str, timeout: int | None = None) -> dict:
    import httpx
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
