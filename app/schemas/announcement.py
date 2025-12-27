from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class AnnouncementCreate(BaseModel):
    title: str
    body: str

class AnnouncementOut(BaseModel):
    id: str
    title: str
    body: str
    image_url: Optional[str] = None
    publish_at: datetime   # НОВОЕ

    class Config:
        from_attributes = True
