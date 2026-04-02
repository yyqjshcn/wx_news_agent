from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from app.schemas.rss_feed import (
    RssFeedCreate, RssFeedUpdate, RssFeedResponse,
    RssFeedTestRequest, RssFeedTestResponse,
)
from app.models.rss_feed import RssFeed
from app.services.rss_service import test_feed
from sqlalchemy import select

router = APIRouter(prefix="/api/rss-feeds", tags=["rss-feeds"])


@router.get("", response_model=list[RssFeedResponse])
async def list_feeds(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(RssFeed).order_by(RssFeed.created_at.desc()))
    return result.scalars().all()


@router.post("", response_model=RssFeedResponse)
async def create_feed(data: RssFeedCreate, db: AsyncSession = Depends(get_db)):
    feed = RssFeed(**data.model_dump())
    db.add(feed)
    await db.commit()
    await db.refresh(feed)
    return feed


@router.patch("/{feed_id}", response_model=RssFeedResponse)
async def update_feed(
    feed_id: str, data: RssFeedUpdate, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(RssFeed).where(RssFeed.id == feed_id))
    feed = result.scalar_one_or_none()
    if not feed:
        raise HTTPException(status_code=404, detail="RSS feed not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(feed, key, value)
    await db.commit()
    await db.refresh(feed)
    return feed


@router.delete("/{feed_id}")
async def delete_feed(feed_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(RssFeed).where(RssFeed.id == feed_id))
    feed = result.scalar_one_or_none()
    if not feed:
        raise HTTPException(status_code=404, detail="RSS feed not found")
    await db.delete(feed)
    await db.commit()
    return {"message": "Deleted"}


@router.post("/test", response_model=RssFeedTestResponse)
async def test_feed_endpoint(data: RssFeedTestRequest):
    result = await test_feed(data.feed_url)
    return result
