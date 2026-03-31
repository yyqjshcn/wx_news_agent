from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from app.schemas.keyword import (
    KeywordCreate, KeywordUpdate, KeywordResponse, KeywordImportRequest,
)
from app.services import keyword_service

router = APIRouter(prefix="/api/keywords", tags=["keywords"])


@router.get("", response_model=list[KeywordResponse])
async def list_keywords(
    skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)
):
    keywords = await keyword_service.get_keywords(db, skip, limit)
    return keywords


@router.post("", response_model=KeywordResponse)
async def create_keyword(
    data: KeywordCreate, db: AsyncSession = Depends(get_db)
):
    keyword = await keyword_service.create_keyword(db, data)
    return keyword


@router.patch("/{keyword_id}", response_model=KeywordResponse)
async def update_keyword(
    keyword_id: str, data: KeywordUpdate, db: AsyncSession = Depends(get_db)
):
    keyword = await keyword_service.update_keyword(db, keyword_id, data)
    if not keyword:
        raise HTTPException(status_code=404, detail="Keyword not found")
    return keyword


@router.delete("/{keyword_id}")
async def delete_keyword(keyword_id: str, db: AsyncSession = Depends(get_db)):
    success = await keyword_service.delete_keyword(db, keyword_id)
    if not success:
        raise HTTPException(status_code=404, detail="Keyword not found")
    return {"message": "Deleted"}


@router.post("/import", response_model=list[KeywordResponse])
async def import_keywords(
    data: KeywordImportRequest, db: AsyncSession = Depends(get_db)
):
    keywords = await keyword_service.import_keywords(db, data.keywords)
    return keywords
