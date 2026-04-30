from pydantic import BaseModel, field_validator
from typing import Optional
from datetime import datetime, timezone


def ensure_utc(v: datetime | None) -> datetime | None:
    if v is None:
        return None
    if v.tzinfo is None:
        return v.replace(tzinfo=timezone.utc)
    return v


class WorkflowBase(BaseModel):
    workflow_name: str
    workflow_type: str
    cron_expression: Optional[str] = ""
    timezone: str = "Asia/Shanghai"
    enabled: bool = True
    config_json: dict = {}


class WorkflowCreate(WorkflowBase):
    pass


class WorkflowUpdate(BaseModel):
    workflow_name: Optional[str] = None
    workflow_type: Optional[str] = None
    cron_expression: Optional[str] = None
    timezone: Optional[str] = None
    enabled: Optional[bool] = None
    config_json: Optional[dict] = None


class WorkflowResponse(WorkflowBase):
    id: str
    last_run_at: Optional[datetime] = None
    last_status: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

    @field_validator("last_run_at", "created_at", "updated_at", mode="before")
    @classmethod
    def make_utc(cls, v):
        return ensure_utc(v)


class WorkflowRunResponse(BaseModel):
    id: str
    workflow_id: str
    trigger_type: str
    status: str
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    error_message: Optional[str] = None
    summary_json: dict = {}
    created_at: datetime

    class Config:
        from_attributes = True

    @field_validator("started_at", "finished_at", "created_at", mode="before")
    @classmethod
    def make_utc(cls, v):
        return ensure_utc(v)
