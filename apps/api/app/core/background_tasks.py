"""
Background task execution for workflow runs.
Replaces Celery task dispatch with asyncio background tasks.
"""
import asyncio
import logging
from datetime import datetime, timezone

from app.db.database import async_session
from app.models.workflow import Workflow, WorkflowRun, WorkflowRunStatus
from app.services.workflow_alert_service import send_workflow_failure_alert

logger = logging.getLogger(__name__)

_running_tasks: dict[str, asyncio.Task] = {}


def _ensure_tz(dt: datetime | None) -> datetime | None:
    """Ensure datetime is timezone-aware (UTC)."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


async def _send_alert_after_close(workflow_id: str, run_id: str, error_message: str, duration_ms: int | None):
    """Send failure alert using a fresh session."""
    try:
        async with async_session() as session:
            workflow = await session.get(Workflow, workflow_id)
            run = await session.get(WorkflowRun, run_id)
            if workflow and run:
                await send_workflow_failure_alert(workflow, run, error_message, duration_ms=duration_ms)
    except Exception as alert_err:
        logger.error(f"Failed to send failure alert for run {run_id}: {alert_err}")


async def _execute_workflow(run_id: str, label: str, task_fn):
    """Execute a workflow task and update run status."""
    async with async_session() as session:
        run = await session.get(WorkflowRun, run_id)
        if not run:
            logger.error(f"Workflow run {run_id} not found")
            return
        workflow_id = run.workflow_id

        run.status = WorkflowRunStatus.RUNNING
        run.started_at = datetime.now(timezone.utc)
        await session.commit()

    try:
        result = await task_fn(workflow_id)

        is_pipeline = (result or {}).get("is_pipeline")
        summary_status = (result or {}).get("status")
        is_failed = not is_pipeline and summary_status in ("failed",)

        async with async_session() as session:
            run = await session.get(WorkflowRun, run_id)
            if not run:
                return

            if not is_pipeline:
                finished_at = datetime.now(timezone.utc)
                if is_failed:
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

        if is_failed:
            await _send_alert_after_close(
                workflow_id, run_id,
                (result or {}).get("message", "Step returned failed status"),
                duration_ms=(result or {}).get("duration_ms"),
            )
    except Exception as e:
        logger.error(f"Workflow run {run_id} ({label}) failed: {e}")

        error_message = str(e)
        alert_workflow_id = None
        alert_duration_ms = None

        async with async_session() as session:
            run = await session.get(WorkflowRun, run_id)
            if not run:
                return

            alert_workflow_id = run.workflow_id
            finished_at = datetime.now(timezone.utc)
            run.status = WorkflowRunStatus.FAILED
            run.finished_at = finished_at
            run.error_message = error_message
            started_at = _ensure_tz(run.started_at)
            if started_at:
                alert_duration_ms = int((finished_at - started_at).total_seconds() * 1000)
                run.duration_ms = alert_duration_ms

            workflow = await session.get(Workflow, alert_workflow_id)
            if workflow:
                workflow.last_run_at = finished_at
                workflow.last_status = WorkflowRunStatus.FAILED.value
                workflow.updated_at = finished_at
                session.add(workflow)

            await session.commit()

        try:
            if alert_workflow_id:
                await _send_alert_after_close(alert_workflow_id, run_id, error_message, duration_ms=alert_duration_ms)
        except Exception as alert_err:
            logger.error(f"Failed to send failure alert for run {run_id}: {alert_err}")


def schedule_workflow_run(run_id: str, label: str, task_fn):
    """Schedule a workflow run as a background task."""
    loop = asyncio.get_event_loop()

    async def run():
        await _execute_workflow(run_id, label, task_fn)

    task = loop.create_task(run())
    _running_tasks[run_id] = task
    task.add_done_callback(lambda t: _running_tasks.pop(run_id, None))
    logger.info(f"Scheduled workflow run {run_id} ({label})")
