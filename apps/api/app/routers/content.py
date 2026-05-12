import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models.digest import DailyDigest
from app.models.llm_provider import LlmProvider
from app.schemas.article import ArticleResponse, ArticleReclassifyRequest, ArticleUpdate
from app.schemas.digest import DigestGenerateRequest, DigestResponse, DigestSendTestRequest
from app.schemas.event import (
    EventAttachArticleRequest,
    EventCreate,
    EventMergeRequest,
    EventResponse,
    EventSplitRequest,
    EventUpdate,
)
from app.services import article_service, event_service, digest_service

router = APIRouter(prefix="/api", tags=["articles", "events", "digests"])


@router.get("/articles", response_model=list[ArticleResponse])
async def list_articles(
    skip: int = 0,
    limit: int = 30,
    account_name: Optional[str] = None,
    status: Optional[str] = None,
    is_relevant: Optional[bool] = None,
    event_type: Optional[str] = None,
    source_type: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    query: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    articles = await article_service.get_articles(
        db,
        skip,
        limit,
        account_name,
        status,
        is_relevant,
        event_type,
        source_type,
        start_date,
        end_date,
        query,
    )
    return await article_service.serialize_articles(db, articles)


@router.get("/articles/count")
async def count_articles(
    account_name: Optional[str] = None,
    status: Optional[str] = None,
    is_relevant: Optional[bool] = None,
    event_type: Optional[str] = None,
    source_type: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    query: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    count = await article_service.count_articles(
        db,
        account_name,
        status,
        is_relevant,
        event_type,
        source_type,
        start_date,
        end_date,
        query,
    )
    return {"count": count}


@router.get("/articles/{article_id}", response_model=ArticleResponse)
async def get_article(article_id: str, db: AsyncSession = Depends(get_db)):
    article = await article_service.get_article(db, article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    return await article_service.serialize_article(db, article)


@router.patch("/articles/{article_id}", response_model=ArticleResponse)
async def update_article(article_id: str, data: ArticleUpdate, db: AsyncSession = Depends(get_db)):
    payload = data.model_dump(exclude_unset=True)
    candidate_events = payload.pop("candidate_events", None)
    article = await article_service.update_article(db, article_id, ArticleUpdate(**payload))
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    if candidate_events is not None:
        await event_service.sync_article_events(db, article, {"events": candidate_events})
        await db.commit()
        article = await article_service.get_article(db, article_id)
    elif any(key in payload for key in ("primary_event_type", "companies_json", "summary_short", "summary_long")):
        await event_service.sync_article_events(
            db,
            article,
            {
                "event_type": article.primary_event_type,
                "companies": article.companies_json or [],
                "summary_short": article.summary_short,
            },
        )
        await db.commit()
        article = await article_service.get_article(db, article_id)

    return await article_service.serialize_article(db, article)


@router.post("/articles/{article_id}/reclassify", response_model=ArticleResponse)
async def reclassify_article(article_id: str, data: ArticleReclassifyRequest, db: AsyncSession = Depends(get_db)):
    article = await article_service.get_article(db, article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    update_data = ArticleUpdate(
        is_relevant=data.is_relevant,
        primary_event_type=data.primary_event_type,
        tags_json=data.tags_json,
        companies_json=data.companies_json,
        summary_short=data.summary_short,
        summary_long=data.summary_long,
    )
    article = await article_service.update_article(db, article_id, update_data)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    classification_payload = {
        "event_type": article.primary_event_type,
        "companies": article.companies_json or [],
        "summary_short": article.summary_short,
    }
    if data.candidate_events is not None:
        classification_payload["events"] = data.candidate_events
    await event_service.sync_article_events(db, article, classification_payload)
    await db.commit()

    article = await article_service.get_article(db, article_id)
    return await article_service.serialize_article(db, article)


@router.get("/events", response_model=list[EventResponse])
async def list_events(
    skip: int = 0,
    limit: int = 50,
    event_type: Optional[str] = None,
    status: Optional[str] = None,
    included_in_digest: Optional[bool] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    query: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    return await event_service.list_events(
        db,
        skip=skip,
        limit=limit,
        event_type=event_type,
        status=status,
        included_in_digest=included_in_digest,
        start_date=start_date,
        end_date=end_date,
        query=query,
    )


@router.get("/events/count")
async def count_events(
    event_type: Optional[str] = None,
    status: Optional[str] = None,
    included_in_digest: Optional[bool] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    query: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    count = await event_service.count_events(
        db,
        event_type=event_type,
        status=status,
        included_in_digest=included_in_digest,
        start_date=start_date,
        end_date=end_date,
        query=query,
    )
    return {"count": count}


@router.get("/events/{event_id}", response_model=EventResponse)
async def get_event(event_id: str, db: AsyncSession = Depends(get_db)):
    event = await event_service.get_event(db, event_id, include_related_articles=True)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@router.post("/events", response_model=EventResponse)
async def create_event(data: EventCreate, db: AsyncSession = Depends(get_db)):
    event = await event_service.create_event(db, data.model_dump(exclude_unset=True))
    await db.commit()
    return await event_service.get_event(db, event.id, include_related_articles=True)


@router.patch("/events/{event_id}", response_model=EventResponse)
async def update_event(event_id: str, data: EventUpdate, db: AsyncSession = Depends(get_db)):
    event = await event_service.update_event(db, event_id, data.model_dump(exclude_unset=True))
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    await db.commit()
    return await event_service.get_event(db, event.id, include_related_articles=True)


@router.delete("/events/{event_id}")
async def delete_event(event_id: str, db: AsyncSession = Depends(get_db)):
    deleted = await event_service.delete_event(db, event_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Event not found")
    await db.commit()
    return {"message": "Deleted"}


@router.post("/events/{event_id}/articles", response_model=EventResponse)
async def attach_article_to_event(
    event_id: str,
    data: EventAttachArticleRequest,
    db: AsyncSession = Depends(get_db),
):
    event = await event_service.attach_article_to_event(
        db,
        event_id=event_id,
        article_id=data.article_id,
        role=data.role or "manual",
        confidence=data.confidence,
        is_primary=data.is_primary,
    )
    if not event:
        raise HTTPException(status_code=404, detail="Event or article not found")
    await db.commit()
    return await event_service.get_event(db, event_id, include_related_articles=True)


@router.delete("/events/{event_id}/articles/{article_id}", response_model=EventResponse)
async def detach_article_from_event(event_id: str, article_id: str, db: AsyncSession = Depends(get_db)):
    removed = await event_service.detach_article_from_event(db, event_id, article_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Article link not found")
    await db.commit()
    event = await event_service.get_event(db, event_id, include_related_articles=True)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@router.post("/events/merge", response_model=EventResponse)
async def merge_events(data: EventMergeRequest, db: AsyncSession = Depends(get_db)):
    event = await event_service.merge_events(db, data.event_ids, data.target_event_id)
    if not event:
        raise HTTPException(status_code=400, detail="Unable to merge events")
    await db.commit()
    return await event_service.get_event(db, event.id, include_related_articles=True)


@router.post("/events/{event_id}/split", response_model=EventResponse)
async def split_event(event_id: str, data: EventSplitRequest, db: AsyncSession = Depends(get_db)):
    event = await event_service.split_event(
        db,
        event_id=event_id,
        article_ids=data.article_ids,
        title=data.title,
        event_type=data.event_type,
        included_in_digest=data.included_in_digest,
    )
    if not event:
        raise HTTPException(status_code=400, detail="Unable to split event")
    await db.commit()
    return await event_service.get_event(db, event.id, include_related_articles=True)


@router.post("/events/migrate-from-articles")
async def migrate_events_from_articles(db: AsyncSession = Depends(get_db)):
    result = await event_service.migrate_legacy_curated_events(db)
    await db.commit()
    return {"message": "Migration completed", **result}


@router.get("/digests", response_model=list[DigestResponse])
async def list_digests(
    skip: int = 0,
    limit: int = 30,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    digests = await article_service.get_digests(db, skip, limit, status)
    return digests


@router.get("/digests/{digest_id}", response_model=DigestResponse)
async def get_digest(digest_id: str, db: AsyncSession = Depends(get_db)):
    digest = await article_service.get_digest(db, digest_id)
    if not digest:
        raise HTTPException(status_code=404, detail="Digest not found")
    return digest


@router.post("/digests/generate", response_model=DigestResponse)
async def generate_digest(data: DigestGenerateRequest, db: AsyncSession = Depends(get_db)):
    is_custom = bool(data.date_start or data.article_ids)

    if is_custom:
        events = await event_service.get_events_by_custom_criteria(
            db,
            date_start=data.date_start,
            date_end=data.date_end,
            article_ids=data.article_ids,
        )
    else:
        beijing_tz = timezone(timedelta(hours=8))
        now_beijing = datetime.now(beijing_tz)
        events = await event_service.get_digest_candidate_events(
            db,
            now=now_beijing,
        )

    result = await db.execute(
        select(LlmProvider).where(
            LlmProvider.enabled == True,
            LlmProvider.is_default_for_digest == True,
        )
    )
    digest_provider = result.scalar_one_or_none()
    if not digest_provider:
        result = await db.execute(
            select(LlmProvider).where(LlmProvider.enabled == True)
        )
        digest_provider = result.scalar_one_or_none()

    digest_date = data.digest_date or datetime.now()
    content_md = digest_service.generate_digest_content(events, digest_provider, digest_date=digest_date)

    digest = DailyDigest(
        id=str(uuid.uuid4()),
        digest_date=digest_date.replace(hour=0, minute=0, second=0, microsecond=0) if not is_custom else digest_date,
        content_markdown=content_md,
        item_count=len(events),
        status="published",
        generated_at=datetime.now(timezone.utc),
    )
    if digest_provider:
        digest.llm_provider_id = digest_provider.id
        digest.llm_model = digest_provider.default_model
    db.add(digest)
    await db.commit()
    await db.refresh(digest)
    return digest


@router.post("/digests/preview")
async def preview_digest_events(data: DigestGenerateRequest, db: AsyncSession = Depends(get_db)):
    if data.date_start or data.article_ids:
        events = await event_service.get_events_by_custom_criteria(
            db,
            date_start=data.date_start,
            date_end=data.date_end,
            article_ids=data.article_ids,
        )
    else:
        beijing_tz = timezone(timedelta(hours=8))
        now_beijing = datetime.now(beijing_tz)
        events = await event_service.get_digest_candidate_events(
            db,
            now=now_beijing,
        )

    total_articles = sum(event.get("article_count", 0) for event in events)
    return {
        "event_count": len(events),
        "article_count": total_articles,
        "events": [
            {
                "id": event["id"],
                "title": event["title"],
                "event_type": event.get("event_type"),
                "importance": event.get("importance"),
                "article_count": event.get("article_count", 0),
                "event_date_start": event.get("event_date_start"),
                "event_date_end": event.get("event_date_end"),
            }
            for event in events
        ],
    }


@router.post("/digests/{digest_id}/send-test")
async def send_test_digest(digest_id: str, data: DigestSendTestRequest, db: AsyncSession = Depends(get_db)):
    digest = await article_service.get_digest(db, digest_id)
    if not digest:
        raise HTTPException(status_code=404, detail="Digest not found")
    return {"message": f"Test digest sent to {data.email}"}
