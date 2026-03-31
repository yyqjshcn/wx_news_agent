import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, JSON, Enum as SAEnum
from app.db.base import Base
import enum


class WorkflowType(str, enum.Enum):
    DAILY_INGEST = "daily_ingest"
    MIDDAY_REFRESH = "midday_refresh"
    CLASSIFY_PENDING = "classify_pending_articles"
    GENERATE_DIGEST = "generate_daily_digest"
    RETRY_FAILED = "retry_failed_jobs"
    LOGIN_HEALTH_CHECK = "login_health_check"


class WorkflowRunStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class TriggerType(str, enum.Enum):
    SCHEDULED = "scheduled"
    MANUAL = "manual"
    RETRY = "retry"


class Workflow(Base):
    __tablename__ = "workflows"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workflow_name = Column(String, nullable=False)
    workflow_type = Column(SAEnum(WorkflowType), nullable=False)
    enabled = Column(Boolean, default=True)
    cron_expression = Column(String, nullable=False)
    timezone = Column(String, default="Asia/Shanghai")
    config_json = Column(JSON, default=dict)
    last_run_at = Column(DateTime(timezone=True), nullable=True)
    last_status = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workflow_id = Column(String, nullable=False)
    trigger_type = Column(SAEnum(TriggerType), nullable=False)
    status = Column(SAEnum(WorkflowRunStatus), default=WorkflowRunStatus.PENDING)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    duration_ms = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    summary_json = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
