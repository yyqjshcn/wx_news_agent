import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from app.db.base import Base


class SourceAccount(Base):
    __tablename__ = "source_accounts"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    account_name = Column(String, nullable=False)
    account_alias = Column(String, nullable=True)
    fakeid = Column(String, nullable=True)
    category = Column(String, nullable=True)
    priority = Column(Integer, default=5)
    enabled = Column(Boolean, default=True)
    last_checked_at = Column(DateTime(timezone=True), nullable=True)
    last_success_at = Column(DateTime(timezone=True), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
