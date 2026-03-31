import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String, Text
from app.db.base import Base


class DailyDigest(Base):
    __tablename__ = "daily_digests"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    digest_date = Column(DateTime(timezone=True), nullable=False)
    content_markdown = Column(Text, nullable=True)
    content_html = Column(Text, nullable=True)
    item_count = Column(Integer, default=0)
    status = Column(String, default="draft")
    llm_provider_id = Column(String, nullable=True)
    llm_model = Column(String, nullable=True)
    generated_at = Column(DateTime(timezone=True), nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
