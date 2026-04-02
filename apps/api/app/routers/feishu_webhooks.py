from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from app.schemas.feishu_webhook import (
    FeishuWebhookCreate, FeishuWebhookUpdate, FeishuWebhookResponse,
    FeishuSendTestRequest,
)
from app.models.feishu_webhook import FeishuWebhook
from app.models.digest import DailyDigest
from app.services.feishu_service import send_digest_to_feishu
from sqlalchemy import select

router = APIRouter(prefix="/api/feishu-webhooks", tags=["feishu-webhooks"])


@router.get("", response_model=list[FeishuWebhookResponse])
async def list_webhooks(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(FeishuWebhook).order_by(FeishuWebhook.created_at.desc()))
    return result.scalars().all()


@router.post("", response_model=FeishuWebhookResponse)
async def create_webhook(data: FeishuWebhookCreate, db: AsyncSession = Depends(get_db)):
    webhook = FeishuWebhook(**data.model_dump())
    db.add(webhook)
    await db.commit()
    await db.refresh(webhook)
    return webhook


@router.patch("/{webhook_id}", response_model=FeishuWebhookResponse)
async def update_webhook(
    webhook_id: str, data: FeishuWebhookUpdate, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(FeishuWebhook).where(FeishuWebhook.id == webhook_id))
    webhook = result.scalar_one_or_none()
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(webhook, key, value)
    await db.commit()
    await db.refresh(webhook)
    return webhook


@router.delete("/{webhook_id}")
async def delete_webhook(webhook_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(FeishuWebhook).where(FeishuWebhook.id == webhook_id))
    webhook = result.scalar_one_or_none()
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    await db.delete(webhook)
    await db.commit()
    return {"message": "Deleted"}


@router.post("/send-digest")
async def send_digest(data: FeishuSendTestRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(FeishuWebhook).where(FeishuWebhook.id == data.webhook_id))
    webhook = result.scalar_one_or_none()
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    if not webhook.enabled:
        raise HTTPException(status_code=400, detail="Webhook is disabled")

    digest_result = await db.execute(select(DailyDigest).where(DailyDigest.id == data.digest_id))
    digest = digest_result.scalar_one_or_none()
    if not digest:
        raise HTTPException(status_code=404, detail="Digest not found")

    res = await send_digest_to_feishu(
        webhook=webhook,
        content_markdown=digest.content_markdown or "",
        digest_date=digest.digest_date.strftime("%Y-%m-%d"),
        item_count=digest.item_count,
    )

    if res.get("success"):
        digest.status = "sent"
        from datetime import datetime, timezone
        digest.sent_at = datetime.now(timezone.utc)
        await db.commit()
        return res
    else:
        raise HTTPException(status_code=500, detail=res.get("error", "Failed to send"))
