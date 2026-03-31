import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from app.db.base import Base


class CuratedEvent(Base):
    __tablename__ = "curated_events"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    article_id = Column(String, nullable=False)
    company_name = Column(String, nullable=True)
    event_type = Column(String, nullable=True)
    importance = Column(Integer, default=3)
    one_line_summary = Column(Text, nullable=True)
    analyst_note = Column(Text, nullable=True)
    included_in_digest = Column(Boolean, default=False)
    event_date = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
