from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from app.services import article_service

router = APIRouter(prefix="/api/wechat", tags=["wechat"])


@router.get("/status")
async def get_login_status(db: AsyncSession = Depends(get_db)):
    return {
        "status": "unknown",
        "last_checked_at": None,
        "last_success_at": None,
        "message": "WeChat adapter not yet configured",
    }


@router.post("/refresh-qr")
async def refresh_qr(db: AsyncSession = Depends(get_db)):
    return {
        "qr_url": "",
        "message": "WeChat adapter not yet configured",
    }


@router.get("/qr")
async def get_qr_image(db: AsyncSession = Depends(get_db)):
    return {"message": "No QR code available"}


@router.post("/check")
async def check_login(db: AsyncSession = Depends(get_db)):
    return {"status": "unknown", "message": "WeChat adapter not yet configured"}


@router.post("/search-account")
async def search_account(query: str, db: AsyncSession = Depends(get_db)):
    return {"results": [], "message": "WeChat adapter not yet configured"}


@router.post("/test-fetch")
async def test_fetch(fakeid: str, db: AsyncSession = Depends(get_db)):
    return {"articles": [], "message": "WeChat adapter not yet configured"}
