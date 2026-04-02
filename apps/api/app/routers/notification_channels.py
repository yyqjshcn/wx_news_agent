from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from app.schemas.notification_channel import (
    NotificationChannelCreate, NotificationChannelUpdate, NotificationChannelResponse,
    NotificationChannelTestRequest, NotificationChannelTestResponse, DigestSendRequest,
)
from app.models.notification_channel import NotificationChannel
from app.models.digest import DailyDigest
from app.services.notification_service import send_to_channel
from sqlalchemy import select

router = APIRouter(prefix="/api/notification-channels", tags=["notification-channels"])


@router.get("", response_model=list[NotificationChannelResponse])
async def list_channels(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(NotificationChannel).order_by(NotificationChannel.created_at.desc()))
    return result.scalars().all()


@router.post("", response_model=NotificationChannelResponse)
async def create_channel(data: NotificationChannelCreate, db: AsyncSession = Depends(get_db)):
    # Check alias uniqueness
    existing = await db.execute(select(NotificationChannel).where(NotificationChannel.alias == data.alias))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"Alias '{data.alias}' already exists")

    channel = NotificationChannel(**data.model_dump())
    db.add(channel)
    await db.commit()
    await db.refresh(channel)
    return channel


@router.patch("/{channel_id}", response_model=NotificationChannelResponse)
async def update_channel(
    channel_id: str, data: NotificationChannelUpdate, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(NotificationChannel).where(NotificationChannel.id == channel_id))
    channel = result.scalar_one_or_none()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    if data.alias and data.alias != channel.alias:
        existing = await db.execute(select(NotificationChannel).where(NotificationChannel.alias == data.alias))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail=f"Alias '{data.alias}' already exists")

    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(channel, key, value)
    await db.commit()
    await db.refresh(channel)
    return channel


@router.delete("/{channel_id}")
async def delete_channel(channel_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(NotificationChannel).where(NotificationChannel.id == channel_id))
    channel = result.scalar_one_or_none()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    await db.delete(channel)
    await db.commit()
    return {"message": "Deleted"}


@router.post("/test", response_model=NotificationChannelTestResponse)
async def test_channel(data: NotificationChannelTestRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(NotificationChannel).where(NotificationChannel.id == data.channel_id))
    channel = result.scalar_one_or_none()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    if not channel.enabled:
        raise HTTPException(status_code=400, detail="Channel is disabled")

    res = await send_to_channel(
        channel,
        data.test_content or "# Test\n\nThis is a test message.",
        "2026-01-01",
        1,
    )
    return res


@router.post("/digests/{digest_id}/send")
async def send_digest_to_channels(
    digest_id: str, data: DigestSendRequest, db: AsyncSession = Depends(get_db)
):
    digest_result = await db.execute(select(DailyDigest).where(DailyDigest.id == digest_id))
    digest = digest_result.scalar_one_or_none()
    if not digest:
        raise HTTPException(status_code=404, detail="Digest not found")

    results = []
    for channel_id in data.channel_ids:
        result = await db.execute(select(NotificationChannel).where(NotificationChannel.id == channel_id))
        channel = result.scalar_one_or_none()
        if not channel:
            results.append({"channel_id": channel_id, "success": False, "error": "Channel not found"})
            continue
        if not channel.enabled:
            results.append({"channel_id": channel_id, "success": False, "error": "Channel disabled"})
            continue

        res = await send_to_channel(
            channel,
            digest.content_markdown or "",
            digest.digest_date.strftime("%Y-%m-%d"),
            digest.item_count,
        )
        results.append({"channel_id": channel_id, **res})

        if res.get("success"):
            digest.status = "sent"
            from datetime import datetime, timezone
            digest.sent_at = datetime.now(timezone.utc)
            await db.commit()

    return {"results": results}
