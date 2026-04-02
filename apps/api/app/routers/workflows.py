from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from app.db.database import get_db
from app.schemas.workflow import (
    WorkflowCreate, WorkflowUpdate, WorkflowResponse, WorkflowRunResponse,
)
from app.services import workflow_service
from app.models.workflow import TriggerType, WorkflowType, WorkflowRunStatus
from app.core.scheduler import run_workflow_task, TASK_MAP, add_workflow_to_scheduler, update_workflow_in_scheduler, remove_workflow_from_scheduler
from app.core.background_tasks import schedule_workflow_run
import logging

logger = logging.getLogger(__name__)

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
    # Add to scheduler if enabled
    if workflow.enabled:
        await add_workflow_to_scheduler(workflow.id)
    return workflow


@router.patch("/{workflow_id}", response_model=WorkflowResponse)
async def update_workflow(
    workflow_id: str, data: WorkflowUpdate, db: AsyncSession = Depends(get_db)
):
    workflow = await workflow_service.update_workflow(db, workflow_id, data)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    # Update scheduler
    await update_workflow_in_scheduler(workflow_id)
    return workflow


@router.delete("/{workflow_id}")
async def delete_workflow(workflow_id: str, db: AsyncSession = Depends(get_db)):
    # Remove from scheduler first
    await remove_workflow_from_scheduler(workflow_id)
    # Then delete from database
    success = await workflow_service.delete_workflow(db, workflow_id)
    if not success:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return {"message": "Deleted"}


@router.post("/{workflow_id}/run")
async def run_workflow(workflow_id: str, db: AsyncSession = Depends(get_db)):
    workflow = await workflow_service.get_workflow(db, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    task_fn = TASK_MAP.get(workflow.workflow_type)
    if not task_fn:
        raise HTTPException(status_code=400, detail=f"Unknown workflow type: {workflow.workflow_type}")
    
    run = await workflow_service.create_workflow_run(db, workflow_id, TriggerType.MANUAL)
    
    schedule_workflow_run(run.id, workflow.workflow_type.value, task_fn)
    
    await workflow_service.update_workflow_run(db, run.id, status=WorkflowRunStatus.RUNNING)
    return {"message": "Workflow run started", "run_id": run.id}


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
