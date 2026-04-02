import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, JSON
from app.db.base import Base


class EmailConfig(Base):
    __tablename__ = "email_configs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    smtp_host = Column(String, nullable=False)
    smtp_port = Column(Integer, default=587)
    use_tls = Column(Boolean, default=True)
    sender_email = Column(String, nullable=False)
    sender_name = Column(String, default="每日摘要")
    sender_password = Column(Text, nullable=False)
    recipients_json = Column(JSON, default=list)
    enabled = Column(Boolean, default=True)
    send_on_digest_generated = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
