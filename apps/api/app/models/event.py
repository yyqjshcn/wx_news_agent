import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
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


class Event(Base):
    __tablename__ = "events"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String, nullable=False)
    event_type = Column(String, nullable=True)
    status = Column(String, default="active")
    importance = Column(Integer, default=3)
    summary_short = Column(Text, nullable=True)
    summary_long = Column(Text, nullable=True)
    analyst_note = Column(Text, nullable=True)
    included_in_digest = Column(Boolean, default=False)
    created_by_strategy = Column(String, default="auto")
    event_date_start = Column(DateTime(timezone=True), nullable=True)
    event_date_end = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class ArticleEvent(Base):
    __tablename__ = "article_events"
    __table_args__ = (
        UniqueConstraint("article_id", "event_id", name="uq_article_events_article_event"),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    article_id = Column(String, nullable=False)
    event_id = Column(String, nullable=False)
    role = Column(String, default="source")
    confidence = Column(Float, nullable=True)
    is_primary = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class EventEntity(Base):
    __tablename__ = "event_entities"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    event_id = Column(String, nullable=False)
    entity_type = Column(String, default="company")
    name = Column(String, nullable=False)
    normalized_name = Column(String, nullable=True)
    role = Column(String, default="participant")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
