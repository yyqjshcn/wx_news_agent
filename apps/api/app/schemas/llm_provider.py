from pydantic import BaseModel, field_validator
from typing import Optional
from datetime import datetime
from app.schemas.utils import ensure_utc


class LlmProviderBase(BaseModel):
    name: str
    base_url: str
    default_model: str
    enabled: bool = True
    is_default_for_relevance: bool = False
    is_default_for_extraction: bool = False
    is_default_for_digest: bool = False
    request_timeout: int = 30
    max_retries: int = 3
    extra_headers_json: dict = {}
    extra_query_json: dict = {}


class LlmProviderCreate(LlmProviderBase):
    api_key: str


class LlmProviderUpdate(BaseModel):
    name: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    default_model: Optional[str] = None
    enabled: Optional[bool] = None
    is_default_for_relevance: Optional[bool] = None
    is_default_for_extraction: Optional[bool] = None
    is_default_for_digest: Optional[bool] = None
    request_timeout: Optional[int] = None
    max_retries: Optional[int] = None
    extra_headers_json: Optional[dict] = None
    extra_query_json: Optional[dict] = None


class LlmProviderResponse(LlmProviderBase):
    id: str
    provider_type: str = "openai_compatible"
    api_key_masked: str
    last_test_status: Optional[str] = None
    last_test_message: Optional[str] = None
    last_test_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

    @field_validator("last_test_at", "created_at", "updated_at", mode="before")
    @classmethod
    def make_utc(cls, v):
        return ensure_utc(v)


class LlmProviderTestRequest(BaseModel):
    prompt: str = "Say 'hello' in one word"
    model: Optional[str] = None


class LlmProviderTestResponse(BaseModel):
    success: bool
    response: Optional[str] = None
    error: Optional[str] = None
    latency_ms: Optional[float] = None
