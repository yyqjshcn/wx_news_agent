from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from app.db.database import get_db
from app.services import article_service

router = APIRouter(prefix="/api", tags=["dashboard", "logs"])


@router.get("/dashboard/stats")
async def get_dashboard_stats(db: AsyncSession = Depends(get_db)):
    stats = await article_service.get_dashboard_stats(db)
    return stats


@router.get("/logs")
async def get_logs(
    skip: int = 0,
    limit: int = 100,
    level: Optional[str] = None,
    module: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    logs = await article_service.get_logs(db, skip, limit, level, module)
    return [
        {
            "id": log.id,
            "level": log.level,
            "module": log.module,
            "message": log.message,
            "payload_json": log.payload_json,
            "created_at": log.created_at,
        }
        for log in logs
    ]
