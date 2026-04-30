"""
Background task execution for workflow runs.
Replaces Celery task dispatch with asyncio background tasks.
"""
import asyncio
import logging
from datetime import datetime, timezone

from app.db.database import async_session
from app.models.workflow import Workflow, WorkflowRun, WorkflowRunStatus

logger = logging.getLogger(__name__)

_running_tasks: dict[str, asyncio.Task] = {}


def _ensure_tz(dt: datetime | None) -> datetime | None:
    """Ensure datetime is timezone-aware (UTC)."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


async def _execute_workflow(run_id: str, label: str, task_fn):
    """Execute a workflow task and update run status."""
    # Look up workflow_id from the run record
    session = async_session()
    try:
        run = await session.get(WorkflowRun, run_id)
        if not run:
            logger.error(f"Workflow run {run_id} not found")
            return
        workflow_id = run.workflow_id
        
        run.status = WorkflowRunStatus.RUNNING
        run.started_at = datetime.now(timezone.utc)
        await session.commit()
    finally:
        await session.close()

    try:
        result = await task_fn(workflow_id)

        session = async_session()
        try:
            run = await session.get(WorkflowRun, run_id)
            if not run:
                return

            is_pipeline = (result or {}).get("is_pipeline")

            if not is_pipeline:
                finished_at = datetime.now(timezone.utc)
                # Check summary for business-level status instead of assuming SUCCESS
                summary_status = (result or {}).get("status")
                if summary_status in ("failed",):
                    run.status = WorkflowRunStatus.FAILED
                    workflow_last_status = WorkflowRunStatus.FAILED.value
                else:
                    run.status = WorkflowRunStatus.SUCCESS
                    workflow_last_status = WorkflowRunStatus.SUCCESS.value

                run.finished_at = finished_at
                run.summary_json = result or {}
                started_at = _ensure_tz(run.started_at)
                if started_at:
                    run.duration_ms = int((finished_at - started_at).total_seconds() * 1000)

                workflow = await session.get(Workflow, workflow_id)
                if workflow:
                    workflow.last_run_at = finished_at
                    workflow.last_status = workflow_last_status
                    workflow.updated_at = finished_at
                    session.add(workflow)

                await session.commit()
            else:
                workflow = await session.get(Workflow, workflow_id)
                if workflow:
                    finished_at = datetime.now(timezone.utc)
                    pipeline_status = (result or {}).get("status", "failed")
                    workflow.last_run_at = finished_at
                    workflow.last_status = WorkflowRunStatus.SUCCESS.value if pipeline_status == "completed" else WorkflowRunStatus.FAILED.value
                    workflow.updated_at = finished_at
                    session.add(workflow)
                await session.commit()
        finally:
            await session.close()
            
    except Exception as e:
        logger.error(f"Workflow run {run_id} ({label}) failed: {e}")
        session = async_session()
        try:
            run = await session.get(WorkflowRun, run_id)
            if not run:
                return
            
            workflow_id = run.workflow_id
            finished_at = datetime.now(timezone.utc)
            run.status = WorkflowRunStatus.FAILED
            run.finished_at = finished_at
            run.error_message = str(e)
            started_at = _ensure_tz(run.started_at)
            if started_at:
                run.duration_ms = int((finished_at - started_at).total_seconds() * 1000)

            workflow = await session.get(Workflow, workflow_id)
            if workflow:
                workflow.last_run_at = finished_at
                workflow.last_status = WorkflowRunStatus.FAILED.value
                workflow.updated_at = finished_at
                session.add(workflow)

            await session.commit()
        finally:
            await session.close()


def schedule_workflow_run(run_id: str, label: str, task_fn):
    """Schedule a workflow run as a background task."""
    loop = asyncio.get_event_loop()
    
    async def run():
        await _execute_workflow(run_id, label, task_fn)
    
    task = loop.create_task(run())
    _running_tasks[run_id] = task
    task.add_done_callback(lambda t: _running_tasks.pop(run_id, None))
    logger.info(f"Scheduled workflow run {run_id} ({label})")
