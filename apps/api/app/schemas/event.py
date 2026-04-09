from pydantic import BaseModel, field_validator
from typing import Optional
from datetime import datetime
from app.schemas.utils import ensure_utc


class EventEntityInput(BaseModel):
    entity_type: str = "company"
    name: str
    normalized_name: Optional[str] = None
    role: str = "participant"


class EventEntityResponse(EventEntityInput):
    id: str


class EventArticleSummary(BaseModel):
    id: str
    title: str
    article_url: str
    account_name: str
    publish_time: Optional[datetime] = None
    summary_short: Optional[str] = None
    primary_event_type: Optional[str] = None

    @field_validator("publish_time", mode="before")
    @classmethod
    def make_publish_time_utc(cls, v):
        return ensure_utc(v)


class EventResponse(BaseModel):
    id: str
    title: str
    event_type: Optional[str] = None
    status: str = "active"
    importance: int = 3
    summary_short: Optional[str] = None
    summary_long: Optional[str] = None
    analyst_note: Optional[str] = None
    included_in_digest: bool = False
    created_by_strategy: str = "auto"
    event_date_start: Optional[datetime] = None
    event_date_end: Optional[datetime] = None
    article_count: int = 0
    latest_article_time: Optional[datetime] = None
    entities: list[EventEntityResponse] = []
    representative_articles: list[EventArticleSummary] = []
    related_articles: list[EventArticleSummary] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

    @field_validator(
        "event_date_start",
        "event_date_end",
        "latest_article_time",
        "created_at",
        "updated_at",
        mode="before",
    )
    @classmethod
    def make_utc(cls, v):
        return ensure_utc(v)


class EventCreate(BaseModel):
    title: Optional[str] = None
    event_type: Optional[str] = None
    status: Optional[str] = "active"
    importance: Optional[int] = None
    summary_short: Optional[str] = None
    summary_long: Optional[str] = None
    analyst_note: Optional[str] = None
    included_in_digest: Optional[bool] = None
    created_by_strategy: Optional[str] = "manual"
    event_date_start: Optional[datetime] = None
    event_date_end: Optional[datetime] = None
    entities: Optional[list[EventEntityInput]] = None

    @field_validator("event_date_start", "event_date_end", mode="before")
    @classmethod
    def make_input_utc(cls, v):
        return ensure_utc(v)


class EventUpdate(BaseModel):
    title: Optional[str] = None
    event_type: Optional[str] = None
    status: Optional[str] = None
    importance: Optional[int] = None
    summary_short: Optional[str] = None
    summary_long: Optional[str] = None
    analyst_note: Optional[str] = None
    included_in_digest: Optional[bool] = None
    created_by_strategy: Optional[str] = None
    event_date_start: Optional[datetime] = None
    event_date_end: Optional[datetime] = None
    entities: Optional[list[EventEntityInput]] = None

    @field_validator("event_date_start", "event_date_end", mode="before")
    @classmethod
    def make_update_utc(cls, v):
        return ensure_utc(v)


class EventAttachArticleRequest(BaseModel):
    article_id: str
    role: Optional[str] = "manual"
    confidence: Optional[float] = None
    is_primary: bool = False


class EventMergeRequest(BaseModel):
    event_ids: list[str]
    target_event_id: Optional[str] = None


class EventSplitRequest(BaseModel):
    article_ids: list[str]
    title: Optional[str] = None
    event_type: Optional[str] = None
    included_in_digest: Optional[bool] = None
