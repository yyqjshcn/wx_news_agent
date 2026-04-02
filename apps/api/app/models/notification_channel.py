import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, JSON
from app.db.base import Base


class NotificationChannel(Base):
    __tablename__ = "notification_channels"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    alias = Column(String, nullable=False, unique=True)
    name = Column(String, nullable=False)
    channel_type = Column(String, nullable=False)  # feishu, wechat_work, dingtalk, slack, discord, custom_webhook, email
    enabled = Column(Boolean, default=True)
    send_on_digest_generated = Column(Boolean, default=False)
    config_json = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
