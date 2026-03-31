from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from app.db.database import get_db
from app.schemas.llm_provider import (
    LlmProviderCreate, LlmProviderUpdate, LlmProviderResponse,
    LlmProviderTestRequest, LlmProviderTestResponse,
)
from app.services import llm_provider_service
from app.services.llm_gateway import test_provider_connectivity

router = APIRouter(prefix="/api/providers", tags=["providers"])


@router.get("", response_model=list[LlmProviderResponse])
async def list_providers(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    providers = await llm_provider_service.get_providers(db, skip, limit)
    return [llm_provider_service.provider_to_response(p) for p in providers]


@router.post("", response_model=LlmProviderResponse)
async def create_provider(
    data: LlmProviderCreate,
    db: AsyncSession = Depends(get_db),
):
    provider = await llm_provider_service.create_provider(db, data)
    return llm_provider_service.provider_to_response(provider)


@router.patch("/{provider_id}", response_model=LlmProviderResponse)
async def update_provider(
    provider_id: str,
    data: LlmProviderUpdate,
    db: AsyncSession = Depends(get_db),
):
    provider = await llm_provider_service.update_provider(db, provider_id, data)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    return llm_provider_service.provider_to_response(provider)


@router.delete("/{provider_id}")
async def delete_provider(
    provider_id: str,
    db: AsyncSession = Depends(get_db),
):
    success = await llm_provider_service.delete_provider(db, provider_id)
    if not success:
        raise HTTPException(status_code=404, detail="Provider not found")
    return {"message": "Deleted"}


@router.post("/{provider_id}/test", response_model=LlmProviderTestResponse)
async def test_provider(
    provider_id: str,
    data: LlmProviderTestRequest,
    db: AsyncSession = Depends(get_db),
):
    provider = await llm_provider_service.get_provider(db, provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    model = data.model or provider.default_model
    result = await test_provider_connectivity(provider, model, data.prompt)
    return result


@router.post("/{provider_id}/set-default")
async def set_default(
    provider_id: str,
    scope: str = Query(default="relevance", description="relevance|extraction|digest"),
    db: AsyncSession = Depends(get_db),
):
    provider = await llm_provider_service.set_default_provider(db, provider_id, scope)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    return {"message": f"Set as default for {scope}"}
