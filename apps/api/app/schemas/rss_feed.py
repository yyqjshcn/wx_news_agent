from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class RssFeedBase(BaseModel):
    name: str
    feed_url: str
    category: Optional[str] = None
    priority: int = 5
    enabled: bool = True
    notes: Optional[str] = None


class RssFeedCreate(RssFeedBase):
    pass


class RssFeedUpdate(BaseModel):
    name: Optional[str] = None
    feed_url: Optional[str] = None
    category: Optional[str] = None
    priority: Optional[int] = None
    enabled: Optional[bool] = None
    notes: Optional[str] = None


class RssFeedResponse(RssFeedBase):
    id: str
    last_checked_at: Optional[datetime] = None
    last_success_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RssFeedTestRequest(BaseModel):
    feed_url: str


class RssFeedTestResponse(BaseModel):
    success: bool
    title: Optional[str] = None
    article_count: Optional[int] = None
    error: Optional[str] = None
