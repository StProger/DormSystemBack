from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class NotificationListItem(BaseModel):
    id: str
    title: str
    created_at: datetime
    is_read: bool
    read_at: Optional[datetime] = None
    preview: str

class NotificationAttachmentOut(BaseModel):
    id: str
    filename: str
    content_type: Optional[str] = None
    size_bytes: Optional[int] = None
    download_url: str

class NotificationDetailOut(BaseModel):
    id: str
    title: str
    body: str
    created_at: datetime
    is_read: bool
    read_at: Optional[datetime] = None
    attachments: list[NotificationAttachmentOut]

class UnreadCountOut(BaseModel):
    unread: int
