import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.keyword import Keyword
from app.schemas.keyword import KeywordCreate, KeywordUpdate


async def get_keywords(db: AsyncSession, skip: int = 0, limit: int = 100) -> list[Keyword]:
    result = await db.execute(select(Keyword).order_by(Keyword.keyword_type, Keyword.weight.desc()).offset(skip).limit(limit))
    return result.scalars().all()


async def get_keyword(db: AsyncSession, keyword_id: str) -> Keyword | None:
    result = await db.execute(select(Keyword).where(Keyword.id == keyword_id))
    return result.scalar_one_or_none()


async def create_keyword(db: AsyncSession, data: KeywordCreate) -> Keyword:
    keyword = Keyword(
        id=str(uuid.uuid4()),
        **data.model_dump(),
    )
    db.add(keyword)
    await db.commit()
    await db.refresh(keyword)
    return keyword


async def update_keyword(db: AsyncSession, keyword_id: str, data: KeywordUpdate) -> Keyword | None:
    keyword = await get_keyword(db, keyword_id)
    if not keyword:
        return None
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if value is not None:
            setattr(keyword, key, value)
    keyword.updated_at = datetime.now(timezone.utc)
    db.add(keyword)
    await db.commit()
    await db.refresh(keyword)
    return keyword


async def delete_keyword(db: AsyncSession, keyword_id: str) -> bool:
    keyword = await get_keyword(db, keyword_id)
    if not keyword:
        return False
    await db.delete(keyword)
    await db.commit()
    return True


async def import_keywords(db: AsyncSession, keywords: list[KeywordCreate]) -> list[Keyword]:
    created = []
    for data in keywords:
        keyword = await create_keyword(db, data)
        created.append(keyword)
    return created
