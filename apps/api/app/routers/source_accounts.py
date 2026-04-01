from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from app.schemas.source_account import (
    SourceAccountCreate, SourceAccountUpdate, SourceAccountResponse,
    SourceAccountResolveRequest,
)
from app.services import source_account_service
from app.services.wechat_adapter import wechat_adapter

router = APIRouter(prefix="/api/source-accounts", tags=["source-accounts"])


@router.get("", response_model=list[SourceAccountResponse])
async def list_accounts(
    skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)
):
    accounts = await source_account_service.get_source_accounts(db, skip, limit)
    return accounts


@router.post("", response_model=SourceAccountResponse)
async def create_account(
    data: SourceAccountCreate, db: AsyncSession = Depends(get_db)
):
    account = await source_account_service.create_source_account(db, data)
    return account


@router.patch("/{account_id}", response_model=SourceAccountResponse)
async def update_account(
    account_id: str, data: SourceAccountUpdate, db: AsyncSession = Depends(get_db)
):
    account = await source_account_service.update_source_account(db, account_id, data)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    return account


@router.delete("/{account_id}")
async def delete_account(account_id: str, db: AsyncSession = Depends(get_db)):
    success = await source_account_service.delete_source_account(db, account_id)
    if not success:
        raise HTTPException(status_code=404, detail="Account not found")
    return {"message": "Deleted"}


@router.post("/{account_id}/resolve-fakeid")
async def resolve_fakeid(
    account_id: str, data: SourceAccountResolveRequest, db: AsyncSession = Depends(get_db)
):
    account = await source_account_service.get_source_account(db, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    account.fakeid = data.fakeid
    db.add(account)
    await db.commit()
    await db.refresh(account)
    return account


@router.get("/search")
async def search_wechat_accounts(query: str, db: AsyncSession = Depends(get_db)):
    results = await wechat_adapter.search_account(query)
    return results


@router.post("/{account_id}/fetch-latest")
async def fetch_latest(account_id: str, db: AsyncSession = Depends(get_db)):
    account = await source_account_service.get_source_account(db, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    if not account.fakeid:
        raise HTTPException(status_code=400, detail="fakeid not set")
    return {"message": "Fetch task queued", "account_id": account_id}
