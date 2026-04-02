import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, JSON
from app.db.base import Base


class FeishuWebhook(Base):
    __tablename__ = "feishu_webhooks"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    webhook_url = Column(Text, nullable=False)
    enabled = Column(Boolean, default=True)
    send_on_digest_generated = Column(Boolean, default=False)
    message_title = Column(String, default="每日摘要")
    include_source_links = Column(Boolean, default=True)
    extra_headers_json = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
