from pydantic import BaseModel
from typing import Optional
from datetime import datetime


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


class DigestGenerateRequest(BaseModel):
    digest_date: Optional[datetime] = None
    llm_provider_id: Optional[str] = None
    llm_model: Optional[str] = None


class DigestSendTestRequest(BaseModel):
    email: str
