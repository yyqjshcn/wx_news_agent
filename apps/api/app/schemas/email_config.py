from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class EmailConfigCreate(BaseModel):
    name: str
    smtp_host: str
    smtp_port: int = 587
    use_tls: bool = True
    sender_email: str
    sender_name: str = "每日摘要"
    sender_password: str
    recipients_json: list[str] = []
    enabled: bool = True
    send_on_digest_generated: bool = False


class EmailConfigUpdate(BaseModel):
    name: Optional[str] = None
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = None
    use_tls: Optional[bool] = None
    sender_email: Optional[str] = None
    sender_name: Optional[str] = None
    sender_password: Optional[str] = None
    recipients_json: Optional[list[str]] = None
    enabled: Optional[bool] = None
    send_on_digest_generated: Optional[bool] = None


class EmailConfigResponse(BaseModel):
    id: str
    name: str
    smtp_host: str
    smtp_port: int
    use_tls: bool
    sender_email: str
    sender_name: str
    recipients_json: list[str]
    enabled: bool
    send_on_digest_generated: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class EmailSendTestRequest(BaseModel):
    config_id: str
    digest_id: str
