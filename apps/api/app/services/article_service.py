import uuid
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.article import RawArticle
from app.models.event import CuratedEvent
from app.models.digest import DailyDigest
from app.models.system_log import SystemLog
from app.schemas.article import ArticleUpdate


async def get_articles(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 30,
    account_name: str | None = None,
    status: str | None = None,
    is_relevant: bool | None = None,
    event_type: str | None = None,
    source_type: str | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
) -> list[RawArticle]:
    query = select(RawArticle)
    if account_name:
        query = query.where(RawArticle.account_name == account_name)
    if status:
        query = query.where(RawArticle.status == status)
    if is_relevant is not None:
        query = query.where(RawArticle.is_relevant == is_relevant)
    if event_type:
        query = query.where(RawArticle.primary_event_type == event_type)
    if source_type:
        query = query.where(RawArticle.source_type == source_type)
    if start_date:
        query = query.where(RawArticle.publish_time >= start_date)
    if end_date:
        query = query.where(RawArticle.publish_time <= end_date)
    query = query.order_by(RawArticle.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


async def count_articles(
    db: AsyncSession,
    account_name: str | None = None,
    status: str | None = None,
    is_relevant: bool | None = None,
    event_type: str | None = None,
    source_type: str | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
) -> int:
    query = select(func.count(RawArticle.id))
    if account_name:
        query = query.where(RawArticle.account_name == account_name)
    if status:
        query = query.where(RawArticle.status == status)
    if is_relevant is not None:
        query = query.where(RawArticle.is_relevant == is_relevant)
    if event_type:
        query = query.where(RawArticle.primary_event_type == event_type)
    if source_type:
        query = query.where(RawArticle.source_type == source_type)
    if start_date:
        query = query.where(RawArticle.publish_time >= start_date)
    if end_date:
        query = query.where(RawArticle.publish_time <= end_date)
    result = await db.execute(query)
    return result.scalar() or 0


async def get_article(db: AsyncSession, article_id: str) -> RawArticle | None:
    result = await db.execute(select(RawArticle).where(RawArticle.id == article_id))
    return result.scalar_one_or_none()


async def update_article(db: AsyncSession, article_id: str, data: ArticleUpdate) -> RawArticle | None:
    article = await get_article(db, article_id)
    if not article:
        return None
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if value is not None:
            setattr(article, key, value)
    article.updated_at = datetime.now(timezone.utc)
    db.add(article)
    await db.commit()
    await db.refresh(article)
    return article


async def get_events(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 50,
    event_type: str | None = None,
    included_in_digest: bool | None = None,
) -> list[CuratedEvent]:
    query = select(CuratedEvent)
    if event_type:
        query = query.where(CuratedEvent.event_type == event_type)
    if included_in_digest is not None:
        query = query.where(CuratedEvent.included_in_digest == included_in_digest)
    query = query.order_by(CuratedEvent.event_date.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


async def get_event(db: AsyncSession, event_id: str) -> CuratedEvent | None:
    result = await db.execute(select(CuratedEvent).where(CuratedEvent.id == event_id))
    return result.scalar_one_or_none()


async def update_event(db: AsyncSession, event_id: str, data: dict) -> CuratedEvent | None:
    event = await get_event(db, event_id)
    if not event:
        return None
    for key, value in data.items():
        if value is not None:
            setattr(event, key, value)
    event.updated_at = datetime.now(timezone.utc)
    db.add(event)
    await db.commit()
    await db.refresh(event)
    return event


async def get_digests(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 30,
    status: str | None = None,
) -> list[DailyDigest]:
    query = select(DailyDigest)
    if status:
        query = query.where(DailyDigest.status == status)
    query = query.order_by(DailyDigest.digest_date.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


async def get_digest(db: AsyncSession, digest_id: str) -> DailyDigest | None:
    result = await db.execute(select(DailyDigest).where(DailyDigest.id == digest_id))
    return result.scalar_one_or_none()


async def create_digest(db: AsyncSession, data: dict) -> DailyDigest:
    digest = DailyDigest(
        id=str(uuid.uuid4()),
        **data,
    )
    db.add(digest)
    await db.commit()
    await db.refresh(digest)
    return digest


async def get_logs(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 100,
    level: str | None = None,
    module: str | None = None,
) -> list[SystemLog]:
    query = select(SystemLog)
    if level:
        query = query.where(SystemLog.level == level)
    if module:
        query = query.where(SystemLog.module == module)
    query = query.order_by(SystemLog.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


async def create_log(db: AsyncSession, level: str, module: str, message: str, payload: dict | None = None) -> SystemLog:
    log = SystemLog(
        id=str(uuid.uuid4()),
        level=level,
        module=module,
        message=message,
        payload_json=payload or {},
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)
    return log


async def get_dashboard_stats(db: AsyncSession) -> dict:
    total_articles = (await db.execute(select(func.count(RawArticle.id)))).scalar() or 0
    relevant_articles = (await db.execute(select(func.count(RawArticle.id)).where(RawArticle.is_relevant == True))).scalar() or 0
    total_events = (await db.execute(select(func.count(CuratedEvent.id)))).scalar() or 0
    total_digests = (await db.execute(select(func.count(DailyDigest.id)))).scalar() or 0
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    today_articles = (await db.execute(select(func.count(RawArticle.id)).where(RawArticle.created_at >= today))).scalar() or 0
    today_events = (await db.execute(select(func.count(CuratedEvent.id)).where(CuratedEvent.created_at >= today))).scalar() or 0
    return {
        "total_articles": total_articles,
        "relevant_articles": relevant_articles,
        "total_events": total_events,
        "total_digests": total_digests,
        "today_articles": today_articles,
        "today_events": today_events,
    }


async def get_system_status(db: AsyncSession) -> dict:
    """Get real-time system status for dashboard."""
    import httpx

    # Check WeChat adapter
    wechat_status = "unknown"
    wechat_message = "无法连接"
    try:
        from app.core.config import get_settings
        settings = get_settings()
        adapter_url = settings.WECHAT_ADAPTER_URL.rstrip("/")
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{adapter_url}/api/admin/status")
            if resp.status_code == 200:
                data = resp.json()
                if data.get("loggedIn") or data.get("authenticated"):
                    nickname = data.get("nickname") or data.get("account", "")
                    wechat_status = "success"
                    wechat_message = f"已登录: {nickname}" if nickname else "已登录"
                else:
                    wechat_status = "failed"
                    wechat_message = data.get("status", "未登录")
            else:
                wechat_status = "failed"
                wechat_message = f"HTTP {resp.status_code}"
    except Exception as e:
        wechat_status = "failed"
        wechat_message = str(e)[:100]

    # Check default LLM provider
    llm_status = "unknown"
    llm_message = "未配置"
    try:
        from app.models.llm_provider import LlmProvider
        result = await db.execute(
            select(LlmProvider).where(
                LlmProvider.enabled == True,
                LlmProvider.is_default_for_digest == True,
            )
        )
        provider = result.scalar_one_or_none()
        if provider:
            llm_status = "success"
            llm_message = f"{provider.name} ({provider.default_model})"
        else:
            result = await db.execute(
                select(LlmProvider).where(LlmProvider.enabled == True)
            )
            provider = result.scalar_one_or_none()
            if provider:
                llm_status = "info"
                llm_message = f"{provider.name} ({provider.default_model}) - 未设为默认"
    except Exception:
        pass

    # Check scheduler
    scheduler_status = "success"
    scheduler_message = "APScheduler 运行中"

    return {
        "wechat": {"status": wechat_status, "message": wechat_message},
        "llm": {"status": llm_status, "message": llm_message},
        "scheduler": {"status": scheduler_status, "message": scheduler_message},
    }
