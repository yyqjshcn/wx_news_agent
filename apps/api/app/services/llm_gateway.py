import httpx
import time
from app.models.llm_provider import LlmProvider
from app.core.security import decrypt_api_key
from app.schemas.llm_provider import LlmProviderTestResponse


async def test_provider_connectivity(
    provider: LlmProvider,
    model: str,
    prompt: str = "Say 'hello' in one word",
) -> LlmProviderTestResponse:
    api_key = decrypt_api_key(provider.api_key_encrypted)
    url = provider.base_url.rstrip("/") + "/chat/completions"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if provider.extra_headers_json:
        headers.update(provider.extra_headers_json)

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 50,
    }

    start = time.time()
    try:
        async with httpx.AsyncClient(timeout=provider.request_timeout) as client:
            response = await client.post(url, json=payload, headers=headers)
            latency_ms = (time.time() - start) * 1000
            response.raise_for_status()
            data = response.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            return LlmProviderTestResponse(
                success=True,
                response=content,
                latency_ms=round(latency_ms, 2),
            )
    except Exception as e:
        latency_ms = (time.time() - start) * 1000
        return LlmProviderTestResponse(
            success=False,
            error=str(e),
            latency_ms=round(latency_ms, 2),
        )


async def call_llm(
    provider: LlmProvider,
    model: str,
    system_prompt: str,
    user_prompt: str,
    response_format: str = "text",
) -> dict:
    api_key = decrypt_api_key(provider.api_key_encrypted)
    url = provider.base_url.rstrip("/") + "/chat/completions"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if provider.extra_headers_json:
        headers.update(provider.extra_headers_json)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": 2000,
    }

    if response_format == "json":
        payload["response_format"] = {"type": "json_object"}

    start = time.time()
    for attempt in range(provider.max_retries):
        try:
            async with httpx.AsyncClient(timeout=provider.request_timeout) as client:
                response = await client.post(url, json=payload, headers=headers)
                latency_ms = (time.time() - start) * 1000
                response.raise_for_status()
                data = response.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                usage = data.get("usage", {})
                return {
                    "success": True,
                    "content": content,
                    "usage": usage,
                    "latency_ms": round(latency_ms, 2),
                    "raw": data,
                }
        except Exception as e:
            if attempt == provider.max_retries - 1:
                latency_ms = (time.time() - start) * 1000
                return {
                    "success": False,
                    "error": str(e),
                    "latency_ms": round(latency_ms, 2),
                }
            await __import__("asyncio").sleep(2 ** attempt)
