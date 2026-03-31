import uuid
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.llm_provider import LlmProvider
from app.schemas.llm_provider import LlmProviderCreate, LlmProviderUpdate
from app.core.security import encrypt_api_key, decrypt_api_key, mask_api_key


async def get_providers(db: AsyncSession, skip: int = 0, limit: int = 100) -> list[LlmProvider]:
    result = await db.execute(select(LlmProvider).order_by(LlmProvider.created_at.desc()).offset(skip).limit(limit))
    return result.scalars().all()


async def get_provider(db: AsyncSession, provider_id: str) -> LlmProvider | None:
    result = await db.execute(select(LlmProvider).where(LlmProvider.id == provider_id))
    return result.scalar_one_or_none()


async def create_provider(db: AsyncSession, data: LlmProviderCreate) -> LlmProvider:
    encrypted_key = encrypt_api_key(data.api_key)
    provider = LlmProvider(
        id=str(uuid.uuid4()),
        name=data.name,
        base_url=data.base_url,
        api_key_encrypted=encrypted_key,
        default_model=data.default_model,
        enabled=data.enabled,
        is_default_for_relevance=data.is_default_for_relevance,
        is_default_for_extraction=data.is_default_for_extraction,
        is_default_for_digest=data.is_default_for_digest,
        request_timeout=data.request_timeout,
        max_retries=data.max_retries,
        extra_headers_json=data.extra_headers_json,
        extra_query_json=data.extra_query_json,
    )
    db.add(provider)
    await db.commit()
    await db.refresh(provider)
    return provider


async def update_provider(db: AsyncSession, provider_id: str, data: LlmProviderUpdate) -> LlmProvider | None:
    provider = await get_provider(db, provider_id)
    if not provider:
        return None
    update_data = data.model_dump(exclude_unset=True)
    if "api_key" in update_data and update_data["api_key"]:
        provider.api_key_encrypted = encrypt_api_key(update_data.pop("api_key"))
    for key, value in update_data.items():
        if value is not None:
            setattr(provider, key, value)
    provider.updated_at = datetime.now(timezone.utc)
    db.add(provider)
    await db.commit()
    await db.refresh(provider)
    return provider


async def delete_provider(db: AsyncSession, provider_id: str) -> bool:
    provider = await get_provider(db, provider_id)
    if not provider:
        return False
    await db.delete(provider)
    await db.commit()
    return True


async def set_default_provider(db: AsyncSession, provider_id: str, scope: str) -> LlmProvider | None:
    provider = await get_provider(db, provider_id)
    if not provider:
        return None
    scope_field = f"is_default_for_{scope}"
    if hasattr(LlmProvider, scope_field):
        await db.execute(
            select(LlmProvider).where(getattr(LlmProvider, scope_field) == True)
        )
        all_providers = (await db.execute(select(LlmProvider))).scalars().all()
        for p in all_providers:
            setattr(p, scope_field, False)
            db.add(p)
        setattr(provider, scope_field, True)
        db.add(provider)
        await db.commit()
        await db.refresh(provider)
    return provider


def provider_to_response(provider: LlmProvider) -> dict:
    decrypted_key = decrypt_api_key(provider.api_key_encrypted)
    return {
        "id": provider.id,
        "name": provider.name,
        "provider_type": provider.provider_type,
        "base_url": provider.base_url,
        "api_key_masked": mask_api_key(decrypted_key),
        "default_model": provider.default_model,
        "enabled": provider.enabled,
        "is_default_for_relevance": provider.is_default_for_relevance,
        "is_default_for_extraction": provider.is_default_for_extraction,
        "is_default_for_digest": provider.is_default_for_digest,
        "request_timeout": provider.request_timeout,
        "max_retries": provider.max_retries,
        "extra_headers_json": provider.extra_headers_json,
        "extra_query_json": provider.extra_query_json,
        "last_test_status": provider.last_test_status,
        "last_test_message": provider.last_test_message,
        "last_test_at": provider.last_test_at,
        "created_at": provider.created_at,
        "updated_at": provider.updated_at,
    }
