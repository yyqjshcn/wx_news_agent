import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.source_account import SourceAccount
from app.schemas.source_account import SourceAccountCreate, SourceAccountUpdate


async def get_source_accounts(db: AsyncSession, skip: int = 0, limit: int = 100) -> list[SourceAccount]:
    result = await db.execute(select(SourceAccount).order_by(SourceAccount.priority.desc()).offset(skip).limit(limit))
    return result.scalars().all()


async def get_source_account(db: AsyncSession, account_id: str) -> SourceAccount | None:
    result = await db.execute(select(SourceAccount).where(SourceAccount.id == account_id))
    return result.scalar_one_or_none()


async def create_source_account(db: AsyncSession, data: SourceAccountCreate) -> SourceAccount:
    account = SourceAccount(
        id=str(uuid.uuid4()),
        **data.model_dump(),
    )
    db.add(account)
    await db.commit()
    await db.refresh(account)
    return account


async def update_source_account(db: AsyncSession, account_id: str, data: SourceAccountUpdate) -> SourceAccount | None:
    account = await get_source_account(db, account_id)
    if not account:
        return None
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if value is not None:
            setattr(account, key, value)
    account.updated_at = datetime.now(timezone.utc)
    db.add(account)
    await db.commit()
    await db.refresh(account)
    return account


async def delete_source_account(db: AsyncSession, account_id: str) -> bool:
    account = await get_source_account(db, account_id)
    if not account:
        return False
    await db.delete(account)
    await db.commit()
    return True
