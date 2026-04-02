from pydantic import BaseModel, field_validator
from typing import Optional
from datetime import datetime
from app.schemas.utils import ensure_utc


class ArticleResponse(BaseModel):
    id: str
    article_url: str
    title: str
    account_name: str
    publish_time: Optional[datetime] = None
    author: Optional[str] = None
    status: str
    is_relevant: Optional[bool] = None
    relevance_score: Optional[float] = None
    primary_event_type: Optional[str] = None
    tags_json: list = []
    companies_json: list = []
    summary_short: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

    @field_validator("publish_time", "created_at", "updated_at", mode="before")
    @classmethod
    def make_utc(cls, v):
        return ensure_utc(v)


class ArticleReclassifyRequest(BaseModel):
    is_relevant: Optional[bool] = None
    primary_event_type: Optional[str] = None
    tags_json: Optional[list] = None


class ArticleUpdate(BaseModel):
    is_relevant: Optional[bool] = None
    primary_event_type: Optional[str] = None
    tags_json: Optional[list] = None
    status: Optional[str] = None
