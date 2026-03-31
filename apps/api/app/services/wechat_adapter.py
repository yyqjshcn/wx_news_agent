import httpx
from typing import Optional
from app.core.config import get_settings


class WechatAdapter:
    def __init__(self):
        self.settings = get_settings()
        self.base_url = self.settings.WECHAT_ADAPTER_URL.rstrip("/")

    async def get_login_status(self) -> dict:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"{self.base_url}/api/status")
                return resp.json()
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def get_login_qr(self) -> Optional[str]:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"{self.base_url}/api/qr")
                data = resp.json()
                return data.get("qr_url") or data.get("qr_base64")
        except Exception:
            return None

    async def search_account(self, query: str) -> list:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(f"{self.base_url}/api/search", json={"query": query})
                return resp.json().get("results", [])
        except Exception:
            return []

    async def get_articles(self, fakeid: str, begin: int = 0, count: int = 5) -> list:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    f"{self.base_url}/api/articles",
                    params={"fakeid": fakeid, "begin": begin, "count": count},
                )
                return resp.json().get("articles", [])
        except Exception:
            return []

    async def get_article_content(self, url: str) -> dict:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(f"{self.base_url}/api/content", json={"url": url})
                return resp.json()
        except Exception:
            return {"error": "Failed to fetch content"}

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{self.base_url}/health")
                return resp.status_code == 200
        except Exception:
            return False


wechat_adapter = WechatAdapter()
