import enum
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, Column, DateTime, Enum as SAEnum, Integer, String, Text, select
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class WorkflowRunStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class Workflow(Base):
    __tablename__ = "workflows"

    id = Column(String, primary_key=True)
    workflow_name = Column(String, nullable=False)
    workflow_type = Column(String, nullable=False)
    last_run_at = Column(DateTime(timezone=True), nullable=True)
    last_status = Column(String, nullable=True)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"

    id = Column(String, primary_key=True)
    workflow_id = Column(String, nullable=False)
    trigger_type = Column(String, nullable=False)
    status = Column(SAEnum(WorkflowRunStatus), default=WorkflowRunStatus.PENDING)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    duration_ms = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    summary_json = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class SourceAccount(Base):
    __tablename__ = "source_accounts"
    id = Column(String, primary_key=True)
    account_name = Column(String, nullable=False)
    account_alias = Column(String, nullable=True)
    fakeid = Column(String, nullable=True)
    category = Column(String, nullable=True)
    priority = Column(Integer, default=5)
    enabled = Column(Boolean, default=True)
    last_checked_at = Column(DateTime(timezone=True), nullable=True)
    last_success_at = Column(DateTime(timezone=True), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class Keyword(Base):
    __tablename__ = "keywords"
    id = Column(String, primary_key=True)
    keyword = Column(String, nullable=False)
    keyword_type = Column(String, nullable=False, default="industry")
    weight = Column(Integer, default=1)
    enabled = Column(Boolean, default=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class RawArticle(Base):
    __tablename__ = "raw_articles"
    id = Column(String, primary_key=True)
    article_url = Column(String, nullable=False, unique=True)
    title = Column(String, nullable=False)
    account_name = Column(String, nullable=False)
    fakeid = Column(String, nullable=True)
    publish_time = Column(DateTime(timezone=True), nullable=True)
    author = Column(String, nullable=True)
    plain_content = Column(Text, nullable=True)
    html_content = Column(Text, nullable=True)
    content_hash = Column(String, nullable=True)
    title_normalized = Column(String, nullable=True)
    fetched_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    status = Column(String, default="new")
    is_relevant = Column(Boolean, nullable=True)
    relevance_score = Column(Integer, nullable=True)
    primary_event_type = Column(String, nullable=True)
    tags_json = Column(JSON, default=list)
    companies_json = Column(JSON, default=list)
    summary_short = Column(Text, nullable=True)
    summary_long = Column(Text, nullable=True)
    llm_provider_id = Column(String, nullable=True)
    llm_model = Column(String, nullable=True)
    raw_llm_output_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


def get_workflow_run(session, run_id: str) -> WorkflowRun | None:
    result = session.execute(select(WorkflowRun).where(WorkflowRun.id == run_id))
    return result.scalar_one_or_none()


def get_workflow(session, workflow_id: str) -> Workflow | None:
    result = session.execute(select(Workflow).where(Workflow.id == workflow_id))
    return result.scalar_one_or_none()
