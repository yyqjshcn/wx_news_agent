from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class KeywordBase(BaseModel):
    keyword: str
    keyword_type: str = "industry"
    weight: int = 1
    enabled: bool = True
    notes: Optional[str] = None


class KeywordCreate(KeywordBase):
    pass


class KeywordUpdate(BaseModel):
    keyword: Optional[str] = None
    keyword_type: Optional[str] = None
    weight: Optional[int] = None
    enabled: Optional[bool] = None
    notes: Optional[str] = None


class KeywordResponse(KeywordBase):
    id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class KeywordImportRequest(BaseModel):
    keywords: list[KeywordCreate]
