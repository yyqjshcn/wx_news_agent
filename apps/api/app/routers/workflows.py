from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from app.db.database import get_db
from app.schemas.workflow import (
    WorkflowCreate, WorkflowUpdate, WorkflowResponse, WorkflowRunResponse,
)
from app.services import workflow_service
from app.models.workflow import TriggerType, WorkflowType, WorkflowRunStatus
from app.core.celery_client import celery_app
import logging

logger = logging.getLogger(__name__)

WORKFLOW_TASK_MAP = {
    WorkflowType.DAILY_INGEST: "app.tasks.daily_ingest",
    WorkflowType.MIDDAY_REFRESH: "app.tasks.daily_ingest",
    WorkflowType.CLASSIFY_PENDING: "app.tasks.classify_article",
    WorkflowType.GENERATE_DIGEST: "app.tasks.generate_daily_digest",
    WorkflowType.RETRY_FAILED: "app.tasks.daily_ingest",
    WorkflowType.LOGIN_HEALTH_CHECK: "app.tasks.check_wechat_login_health",
}

router = APIRouter(prefix="/api/workflows", tags=["workflows"])


@router.get("", response_model=list[WorkflowResponse])
async def list_workflows(db: AsyncSession = Depends(get_db)):
    workflows = await workflow_service.get_workflows(db)
    return workflows


@router.post("", response_model=WorkflowResponse)
async def create_workflow(
    data: WorkflowCreate, db: AsyncSession = Depends(get_db)
):
    workflow = await workflow_service.create_workflow(db, data)
    return workflow


@router.patch("/{workflow_id}", response_model=WorkflowResponse)
async def update_workflow(
    workflow_id: str, data: WorkflowUpdate, db: AsyncSession = Depends(get_db)
):
    workflow = await workflow_service.update_workflow(db, workflow_id, data)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return workflow


@router.delete("/{workflow_id}")
async def delete_workflow(workflow_id: str, db: AsyncSession = Depends(get_db)):
    success = await workflow_service.delete_workflow(db, workflow_id)
    if not success:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return {"message": "Deleted"}


@router.post("/{workflow_id}/run")
async def run_workflow(workflow_id: str, db: AsyncSession = Depends(get_db)):
    workflow = await workflow_service.get_workflow(db, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    run = await workflow_service.create_workflow_run(db, workflow_id, TriggerType.MANUAL)
    
    task_name = WORKFLOW_TASK_MAP.get(workflow.workflow_type)
    if not task_name:
        raise HTTPException(status_code=400, detail=f"Unknown workflow type: {workflow.workflow_type}")
    
    try:
        celery_app.send_task(task_name, args=[run.id])
        await workflow_service.update_workflow_run(db, run.id, status=WorkflowRunStatus.RUNNING)
        return {"message": "Workflow run started", "run_id": run.id}
    except Exception as e:
        logger.error(f"Failed to dispatch task for run {run.id}: {e}")
        await workflow_service.update_workflow_run(db, run.id, status=WorkflowRunStatus.FAILED, error_message=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to dispatch task: {e}")


@router.get("/{workflow_id}/runs", response_model=list[WorkflowRunResponse])
async def get_workflow_runs(
    workflow_id: str,
    skip: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    workflow = await workflow_service.get_workflow(db, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    runs = await workflow_service.get_workflow_runs(db, workflow_id, skip, limit)
    return runs
