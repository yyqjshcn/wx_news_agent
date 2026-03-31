import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from app.db.database import get_db
from app.core.config import get_settings

router = APIRouter(prefix="/api/wechat", tags=["wechat"])

settings = get_settings()
adapter_url = settings.WECHAT_ADAPTER_URL.rstrip("/")


class SearchRequest(BaseModel):
    query: str


class TestFetchRequest(BaseModel):
    fakeid: str


@router.get("/status")
async def get_login_status(db: AsyncSession = Depends(get_db)):
    """Get WeChat login status from adapter /api/admin/status"""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{adapter_url}/api/admin/status")
            data = resp.json()
            # /api/admin/status returns: authenticated, loggedIn, isExpired, status, nickname, fakeid, expireTime
            is_logged_in = data.get("authenticated", False) or data.get("loggedIn", False)
            is_expired = data.get("isExpired", True)
            adapter_status = data.get("status", "")
            nickname = data.get("nickname", "")
            fakeid = data.get("fakeid", "")
            expire_time = data.get("expireTime", 0)

            if is_logged_in and not is_expired:
                status = "logged_in"
                message = f"已登录: {nickname}" if nickname else "已登录"
            elif is_expired:
                status = "expired"
                message = adapter_status or "会话已过期"
            else:
                status = "unknown"
                message = adapter_status or "状态未知"

            return {
                "status": status,
                "expire_time": expire_time,
                "nickname": nickname,
                "fakeid": fakeid,
                "last_checked_at": None,
                "last_success_at": None,
                "message": message,
            }
    except Exception as e:
        return {
            "status": "error",
            "message": f"无法连接微信适配器: {str(e)}",
        }


@router.post("/refresh-qr")
async def refresh_qr(db: AsyncSession = Depends(get_db)):
    """Check adapter health - QR generation requires browser cookies, done via /api/login/*"""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{adapter_url}/api/health")
            if resp.status_code == 200:
                return {
                    "qr_url": "",
                    "message": "适配器就绪，请在页面点击「开始登录」扫码",
                    "adapter_ready": True,
                }
            return {
                "qr_url": "",
                "message": "适配器响应异常",
                "adapter_ready": False,
            }
    except Exception as e:
        return {
            "qr_url": "",
            "message": f"无法连接微信适配器: {str(e)}",
            "adapter_ready": False,
        }


@router.post("/check")
async def check_login(db: AsyncSession = Depends(get_db)):
    status = await get_login_status(db)
    return status


@router.post("/search-account")
async def search_account(req: SearchRequest, db: AsyncSession = Depends(get_db)):
    """Search WeChat accounts via adapter /api/public/searchbiz"""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{adapter_url}/api/public/searchbiz",
                params={"query": req.query}
            )
            data = resp.json()
            return {"results": data.get("list", [])}
    except Exception as e:
        return {"results": [], "message": f"搜索失败: {str(e)}"}


@router.post("/test-fetch")
async def test_fetch(req: TestFetchRequest, db: AsyncSession = Depends(get_db)):
    """Get articles via adapter /api/public/articles"""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{adapter_url}/api/public/articles",
                params={"fakeid": req.fakeid, "begin": 0, "count": 5}
            )
            data = resp.json()
            return {"articles": data.get("list", data.get("articles", []))}
    except Exception as e:
        return {"articles": [], "message": f"获取文章失败: {str(e)}"}
