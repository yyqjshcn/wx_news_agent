from pydantic import BaseModel
from typing import Optional
from datetime import datetime


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


class EventUpdate(BaseModel):
    company_name: Optional[str] = None
    event_type: Optional[str] = None
    importance: Optional[int] = None
    one_line_summary: Optional[str] = None
    analyst_note: Optional[str] = None
    included_in_digest: Optional[bool] = None
