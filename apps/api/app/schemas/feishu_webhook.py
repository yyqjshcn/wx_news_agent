from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class FeishuWebhookCreate(BaseModel):
    name: str
    webhook_url: str
    enabled: bool = True
    send_on_digest_generated: bool = False
    message_title: str = "每日摘要"
    include_source_links: bool = True
    extra_headers_json: dict = {}


class FeishuWebhookUpdate(BaseModel):
    name: Optional[str] = None
    webhook_url: Optional[str] = None
    enabled: Optional[bool] = None
    send_on_digest_generated: Optional[bool] = None
    message_title: Optional[str] = None
    include_source_links: Optional[bool] = None
    extra_headers_json: Optional[dict] = None


class FeishuWebhookResponse(BaseModel):
    id: str
    name: str
    webhook_url: str
    enabled: bool
    send_on_digest_generated: bool
    message_title: str
    include_source_links: bool
    extra_headers_json: dict
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class FeishuSendTestRequest(BaseModel):
    webhook_id: str
    digest_id: str
