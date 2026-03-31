import httpx
from typing import Optional
from app.core.config import get_settings


class WechatAdapter:
    def __init__(self):
        self.settings = get_settings()
        self.base_url = self.settings.WECHAT_ADAPTER_URL.rstrip("/")

    async def get_login_status(self) -> dict:
        """Get WeChat login status via /api/admin/status"""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"{self.base_url}/api/admin/status")
                data = resp.json()
                # Map the adapter response to our expected format
                is_expired = data.get("isExpired", True)
                expire_time = data.get("expireTime")
                if is_expired:
                    status = "expired"
                    message = data.get("message", "Login expired")
                else:
                    status = "logged_in"
                    message = data.get("message", "Logged in")
                return {
                    "status": status,
                    "expire_time": expire_time,
                    "last_checked_at": None,
                    "last_success_at": None,
                    "message": message,
                }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to connect to WeChat adapter: {str(e)}",
            }

    async def get_login_qr(self) -> Optional[str]:
        """Get QR code by initializing a login session and fetching QR.
        
        Flow: POST /api/login/session/{id} -> GET /api/login/getqrcode
        """
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                # Step 1: Initialize login session
                session_resp = await client.post(f"{self.base_url}/api/login/session/default")
                session_data = session_resp.json()
                session_id = session_data.get("id") or session_data.get("session_id") or "default"

                # Step 2: Get QR code
                qr_resp = await client.get(f"{self.base_url}/api/login/getqrcode", params={"id": session_id})
                qr_data = qr_resp.json()
                
                # The QR code may be returned as a URL or base64 image
                qr_url = qr_data.get("qr_url") or qr_data.get("qrcode") or qr_data.get("qr_base64")
                if qr_url and not qr_url.startswith(("http://", "https://", "data:")):
                    qr_url = f"data:image/png;base64,{qr_url}"
                return qr_url
        except Exception as e:
            return None

    async def check_login(self) -> dict:
        """Check login scan status via /api/login/scan"""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"{self.base_url}/api/login/scan")
                return resp.json()
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def complete_login(self, session_id: str = "default") -> dict:
        """Complete login via POST /api/login/bizlogin"""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    f"{self.base_url}/api/login/bizlogin",
                    json={"id": session_id}
                )
                return resp.json()
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def search_account(self, query: str) -> list:
        """Search WeChat accounts via GET /api/public/searchbiz"""
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    f"{self.base_url}/api/public/searchbiz",
                    params={"query": query}
                )
                data = resp.json()
                return data.get("list", [])
        except Exception:
            return []

    async def get_articles(self, fakeid: str, begin: int = 0, count: int = 5) -> list:
        """Get articles via GET /api/public/articles"""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    f"{self.base_url}/api/public/articles",
                    params={"fakeid": fakeid, "begin": begin, "count": count},
                )
                return resp.json().get("list", resp.json().get("articles", []))
        except Exception:
            return []

    async def get_article_content(self, url: str) -> dict:
        """Get article content via POST /api/article"""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{self.base_url}/api/article",
                    json={"url": url}
                )
                return resp.json()
        except Exception:
            return {"error": "Failed to fetch content"}

    async def health_check(self) -> bool:
        """Health check via GET /api/health"""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{self.base_url}/api/health")
                return resp.status_code == 200
        except Exception:
            return False


wechat_adapter = WechatAdapter()
