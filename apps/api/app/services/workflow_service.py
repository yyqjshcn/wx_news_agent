import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.workflow import Workflow, WorkflowRun, WorkflowType, WorkflowRunStatus, TriggerType
from app.schemas.workflow import WorkflowCreate, WorkflowUpdate


async def get_workflows(db: AsyncSession) -> list[Workflow]:
    result = await db.execute(select(Workflow).order_by(Workflow.created_at.desc()))
    return result.scalars().all()


async def get_workflow(db: AsyncSession, workflow_id: str) -> Workflow | None:
    result = await db.execute(select(Workflow).where(Workflow.id == workflow_id))
    return result.scalar_one_or_none()


async def create_workflow(db: AsyncSession, data: WorkflowCreate) -> Workflow:
    workflow = Workflow(
        id=str(uuid.uuid4()),
        workflow_type=WorkflowType(data.workflow_type),
        **data.model_dump(exclude={"workflow_type"}),
    )
    db.add(workflow)
    await db.commit()
    await db.refresh(workflow)
    return workflow


async def update_workflow(db: AsyncSession, workflow_id: str, data: WorkflowUpdate) -> Workflow | None:
    workflow = await get_workflow(db, workflow_id)
    if not workflow:
        return None
    update_data = data.model_dump(exclude_unset=True)
    if "workflow_type" in update_data:
        update_data["workflow_type"] = WorkflowType(update_data.pop("workflow_type"))
    for key, value in update_data.items():
        if value is not None:
            setattr(workflow, key, value)
    workflow.updated_at = datetime.now(timezone.utc)
    db.add(workflow)
    await db.commit()
    await db.refresh(workflow)
    return workflow


async def delete_workflow(db: AsyncSession, workflow_id: str) -> bool:
    workflow = await get_workflow(db, workflow_id)
    if not workflow:
        return False
    await db.delete(workflow)
    await db.commit()
    return True


async def get_workflow_runs(db: AsyncSession, workflow_id: str, skip: int = 0, limit: int = 20) -> list[WorkflowRun]:
    result = await db.execute(
        select(WorkflowRun)
        .where(WorkflowRun.workflow_id == workflow_id)
        .order_by(WorkflowRun.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()


async def create_workflow_run(
    db: AsyncSession, workflow_id: str, trigger_type: TriggerType = TriggerType.MANUAL
) -> WorkflowRun:
    run = WorkflowRun(
        id=str(uuid.uuid4()),
        workflow_id=workflow_id,
        trigger_type=trigger_type,
        status=WorkflowRunStatus.PENDING,
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)
    return run


async def update_workflow_run(db: AsyncSession, run_id: str, **kwargs) -> WorkflowRun | None:
    result = await db.execute(select(WorkflowRun).where(WorkflowRun.id == run_id))
    run = result.scalar_one_or_none()
    if not run:
        return None
    for key, value in kwargs.items():
        setattr(run, key, value)
    db.add(run)
    await db.commit()
    await db.refresh(run)
    return run
