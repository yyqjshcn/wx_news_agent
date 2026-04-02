from pydantic import BaseModel, field_validator
from typing import Optional
from datetime import datetime
from app.schemas.utils import ensure_utc


class EventResponse(BaseModel):
    id: str
    article_id: str
    company_name: Optional[str] = None
    event_type: Optional[str] = None
    importance: int = 3
    one_line_summary: Optional[str] = None
    analyst_note: Optional[str] = None
    included_in_digest: bool = False
    event_date: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

    @field_validator("event_date", "created_at", "updated_at", mode="before")
    @classmethod
    def make_utc(cls, v):
        return ensure_utc(v)


class EventUpdate(BaseModel):
    company_name: Optional[str] = None
    event_type: Optional[str] = None
    importance: Optional[int] = None
    one_line_summary: Optional[str] = None
    analyst_note: Optional[str] = None
    included_in_digest: Optional[bool] = None
