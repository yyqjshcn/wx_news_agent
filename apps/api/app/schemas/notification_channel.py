from pydantic import BaseModel
from typing import Optional
from datetime import datetime


CHANNEL_TYPES = [
    "feishu",
    "wechat_work",
    "dingtalk",
    "slack",
    "discord",
    "custom_webhook",
    "email",
]


class NotificationChannelBase(BaseModel):
    alias: str
    name: str
    channel_type: str
    enabled: bool = True
    send_on_digest_generated: bool = False
    config_json: dict = {}


class NotificationChannelCreate(NotificationChannelBase):
    pass


class NotificationChannelUpdate(BaseModel):
    alias: Optional[str] = None
    name: Optional[str] = None
    channel_type: Optional[str] = None
    enabled: Optional[bool] = None
    send_on_digest_generated: Optional[bool] = None
    config_json: Optional[dict] = None


class NotificationChannelResponse(NotificationChannelBase):
    id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class NotificationChannelTestRequest(BaseModel):
    channel_id: str
    test_content: Optional[str] = None


class NotificationChannelTestResponse(BaseModel):
    success: bool
    message: Optional[str] = None
    error: Optional[str] = None


class DigestSendRequest(BaseModel):
    channel_ids: list[str]
