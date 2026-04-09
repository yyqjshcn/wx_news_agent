from pydantic import BaseModel, field_validator
from typing import Optional
from datetime import datetime
from app.schemas.utils import ensure_utc


class LinkedEventSummary(BaseModel):
    id: str
    title: str
    event_type: Optional[str] = None
    importance: int = 3
    included_in_digest: bool = False
    event_date_start: Optional[datetime] = None
    event_date_end: Optional[datetime] = None
    entity_names: list[str] = []

    @field_validator("event_date_start", "event_date_end", mode="before")
    @classmethod
    def make_event_dates_utc(cls, v):
        return ensure_utc(v)


class ArticleResponse(BaseModel):
    id: str
    article_url: str
    title: str
    account_name: str
    source_type: str = "wechat"
    publish_time: Optional[datetime] = None
    author: Optional[str] = None
    status: str
    is_relevant: Optional[bool] = None
    relevance_score: Optional[float] = None
    primary_event_type: Optional[str] = None
    tags_json: list = []
    companies_json: list = []
    summary_short: Optional[str] = None
    summary_long: Optional[str] = None
    linked_events: list[LinkedEventSummary] = []
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
    companies_json: Optional[list] = None
    summary_short: Optional[str] = None
    summary_long: Optional[str] = None
    candidate_events: Optional[list[dict]] = None


class ArticleUpdate(BaseModel):
    is_relevant: Optional[bool] = None
    primary_event_type: Optional[str] = None
    tags_json: Optional[list] = None
    companies_json: Optional[list] = None
    summary_short: Optional[str] = None
    summary_long: Optional[str] = None
    status: Optional[str] = None
    candidate_events: Optional[list[dict]] = None
