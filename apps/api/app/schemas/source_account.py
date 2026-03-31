from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class SourceAccountBase(BaseModel):
    account_name: str
    account_alias: Optional[str] = None
    category: Optional[str] = None
    priority: int = 5
    enabled: bool = True
    notes: Optional[str] = None


class SourceAccountCreate(SourceAccountBase):
    pass


class SourceAccountUpdate(BaseModel):
    account_name: Optional[str] = None
    account_alias: Optional[str] = None
    fakeid: Optional[str] = None
    category: Optional[str] = None
    priority: Optional[int] = None
    enabled: Optional[bool] = None
    notes: Optional[str] = None


class SourceAccountResponse(SourceAccountBase):
    id: str
    fakeid: Optional[str] = None
    last_checked_at: Optional[datetime] = None
    last_success_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SourceAccountResolveRequest(BaseModel):
    fakeid: str
