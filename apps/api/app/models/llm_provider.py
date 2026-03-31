import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text, JSON
from app.db.base import Base


class LlmProvider(Base):
    __tablename__ = "llm_providers"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    provider_type = Column(String, nullable=False, default="openai_compatible")
    base_url = Column(String, nullable=False)
    api_key_encrypted = Column(Text, nullable=False)
    default_model = Column(String, nullable=False)
    enabled = Column(Boolean, default=True)
    is_default_for_relevance = Column(Boolean, default=False)
    is_default_for_extraction = Column(Boolean, default=False)
    is_default_for_digest = Column(Boolean, default=False)
    request_timeout = Column(Integer, default=30)
    max_retries = Column(Integer, default=3)
    extra_headers_json = Column(JSON, default=dict)
    extra_query_json = Column(JSON, default=dict)
    last_test_status = Column(String, nullable=True)
    last_test_message = Column(Text, nullable=True)
    last_test_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
