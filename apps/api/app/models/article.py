import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text, JSON
from app.db.base import Base


class RawArticle(Base):
    __tablename__ = "raw_articles"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    article_url = Column(String, nullable=False, unique=True)
    title = Column(String, nullable=False)
    account_name = Column(String, nullable=False)
    fakeid = Column(String, nullable=True)
    publish_time = Column(DateTime(timezone=True), nullable=True)
    author = Column(String, nullable=True)
    plain_content = Column(Text, nullable=True)
    html_content = Column(Text, nullable=True)
    content_hash = Column(String, nullable=True)
    title_normalized = Column(String, nullable=True)
    fetched_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    status = Column(String, default="new")
    is_relevant = Column(Boolean, nullable=True)
    relevance_score = Column(Float, nullable=True)
    primary_event_type = Column(String, nullable=True)
    tags_json = Column(JSON, default=list)
    companies_json = Column(JSON, default=list)
    summary_short = Column(Text, nullable=True)
    summary_long = Column(Text, nullable=True)
    llm_provider_id = Column(String, nullable=True)
    llm_model = Column(String, nullable=True)
    raw_llm_output_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
