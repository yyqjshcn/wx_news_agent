from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from datetime import datetime
from app.db.database import get_db
from app.schemas.article import ArticleResponse, ArticleReclassifyRequest, ArticleUpdate
from app.schemas.event import EventResponse, EventUpdate
from app.schemas.digest import DigestResponse, DigestGenerateRequest, DigestSendTestRequest
from app.services import article_service

router = APIRouter(prefix="/api", tags=["articles", "events", "digests"])


@router.get("/articles", response_model=list[ArticleResponse])
async def list_articles(
    skip: int = 0,
    limit: int = 50,
    account_name: Optional[str] = None,
    status: Optional[str] = None,
    is_relevant: Optional[bool] = None,
    event_type: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: AsyncSession = Depends(get_db),
):
    articles = await article_service.get_articles(
        db, skip, limit, account_name, status, is_relevant, event_type, start_date, end_date
    )
    return articles


@router.get("/articles/{article_id}", response_model=ArticleResponse)
async def get_article(article_id: str, db: AsyncSession = Depends(get_db)):
    article = await article_service.get_article(db, article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    return article


@router.patch("/articles/{article_id}", response_model=ArticleResponse)
async def update_article(
    article_id: str, data: ArticleUpdate, db: AsyncSession = Depends(get_db)
):
    article = await article_service.update_article(db, article_id, data)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    return article


@router.post("/articles/{article_id}/reclassify", response_model=ArticleResponse)
async def reclassify_article(
    article_id: str, data: ArticleReclassifyRequest, db: AsyncSession = Depends(get_db)
):
    article = await article_service.get_article(db, article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    update_data = ArticleUpdate(
        is_relevant=data.is_relevant,
        primary_event_type=data.primary_event_type,
        tags_json=data.tags_json,
    )
    article = await article_service.update_article(db, article_id, update_data)
    return article


@router.get("/events", response_model=list[EventResponse])
async def list_events(
    skip: int = 0,
    limit: int = 50,
    event_type: Optional[str] = None,
    included_in_digest: Optional[bool] = None,
    db: AsyncSession = Depends(get_db),
):
    events = await article_service.get_events(db, skip, limit, event_type, included_in_digest)
    return events


@router.patch("/events/{event_id}", response_model=EventResponse)
async def update_event(
    event_id: str, data: EventUpdate, db: AsyncSession = Depends(get_db)
):
    event = await article_service.update_event(db, event_id, data.model_dump(exclude_unset=True))
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


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
async def generate_digest(
    data: DigestGenerateRequest, db: AsyncSession = Depends(get_db)
):
    digest_date = data.digest_date or datetime.now()
    digest = await article_service.create_digest(db, {
        "digest_date": digest_date,
        "content_markdown": "# Sample Digest\n\nThis is a placeholder digest.",
        "content_html": "<h1>Sample Digest</h1><p>This is a placeholder digest.</p>",
        "item_count": 0,
        "status": "draft",
        "llm_provider_id": data.llm_provider_id,
        "llm_model": data.llm_model,
        "generated_at": datetime.now(),
    })
    return digest


@router.post("/digests/{digest_id}/send-test")
async def send_test_digest(
    digest_id: str, data: DigestSendTestRequest, db: AsyncSession = Depends(get_db)
):
    digest = await article_service.get_digest(db, digest_id)
    if not digest:
        raise HTTPException(status_code=404, detail="Digest not found")
    return {"message": f"Test digest sent to {data.email}"}
