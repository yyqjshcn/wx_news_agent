from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from app.schemas.email_config import (
    EmailConfigCreate, EmailConfigUpdate, EmailConfigResponse,
    EmailSendTestRequest,
)
from app.models.email_config import EmailConfig
from app.models.digest import DailyDigest
from app.services.email_service import send_digest_email
from app.core.security import encrypt_api_key
from sqlalchemy import select

router = APIRouter(prefix="/api/email-configs", tags=["email-configs"])


@router.get("", response_model=list[EmailConfigResponse])
async def list_configs(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(EmailConfig).order_by(EmailConfig.created_at.desc()))
    configs = result.scalars().all()
    return configs


@router.post("", response_model=EmailConfigResponse)
async def create_config(data: EmailConfigCreate, db: AsyncSession = Depends(get_db)):
    config_dict = data.model_dump()
    config_dict["sender_password"] = encrypt_api_key(data.sender_password)
    config = EmailConfig(**config_dict)
    db.add(config)
    await db.commit()
    await db.refresh(config)
    return config


@router.patch("/{config_id}", response_model=EmailConfigResponse)
async def update_config(
    config_id: str, data: EmailConfigUpdate, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(EmailConfig).where(EmailConfig.id == config_id))
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="Email config not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        if key == "sender_password":
            setattr(config, key, encrypt_api_key(value))
        else:
            setattr(config, key, value)
    await db.commit()
    await db.refresh(config)
    return config


@router.delete("/{config_id}")
async def delete_config(config_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(EmailConfig).where(EmailConfig.id == config_id))
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="Email config not found")
    await db.delete(config)
    await db.commit()
    return {"message": "Deleted"}


@router.post("/send-digest")
async def send_digest(data: EmailSendTestRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(EmailConfig).where(EmailConfig.id == data.config_id))
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="Email config not found")
    if not config.enabled:
        raise HTTPException(status_code=400, detail="Email config is disabled")

    digest_result = await db.execute(select(DailyDigest).where(DailyDigest.id == data.digest_id))
    digest = digest_result.scalar_one_or_none()
    if not digest:
        raise HTTPException(status_code=404, detail="Digest not found")

    res = await send_digest_email(
        config=config,
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
