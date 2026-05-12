from pydantic import BaseModel, field_validator
from typing import Optional
from datetime import datetime
from app.schemas.utils import ensure_utc


class DigestResponse(BaseModel):
    id: str
    digest_date: datetime
    content_markdown: Optional[str] = None
    content_html: Optional[str] = None
    item_count: int = 0
    status: str = "draft"
    llm_provider_id: Optional[str] = None
    llm_model: Optional[str] = None
    generated_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

    @field_validator("digest_date", "generated_at", "sent_at", "created_at", "updated_at", mode="before")
    @classmethod
    def make_utc(cls, v):
        return ensure_utc(v)


class DigestGenerateRequest(BaseModel):
    digest_date: Optional[datetime] = None
    date_start: Optional[datetime] = None
    date_end: Optional[datetime] = None
    article_ids: Optional[list[str]] = None
    llm_provider_id: Optional[str] = None
    llm_model: Optional[str] = None


class DigestSendTestRequest(BaseModel):
    email: str
