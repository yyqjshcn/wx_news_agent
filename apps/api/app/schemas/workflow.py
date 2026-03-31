from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class WorkflowBase(BaseModel):
    workflow_name: str
    workflow_type: str
    cron_expression: str
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
