from pydantic import BaseModel
from typing import Optional
from datetime import datetime


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


class ArticleReclassifyRequest(BaseModel):
    is_relevant: Optional[bool] = None
    primary_event_type: Optional[str] = None
    tags_json: Optional[list] = None


class ArticleUpdate(BaseModel):
    is_relevant: Optional[bool] = None
    primary_event_type: Optional[str] = None
    tags_json: Optional[list] = None
    status: Optional[str] = None
