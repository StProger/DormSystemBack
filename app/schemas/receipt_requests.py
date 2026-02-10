from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class ReceiptRequestCreate(BaseModel):
    period: Optional[str] = None
    comment: Optional[str] = None
    send_to_email: bool = False

class ReceiptRequestOut(BaseModel):
    id: str
    period: Optional[str] = None
    comment: Optional[str] = None
    status: str
    created_at: datetime
    processed_at: Optional[datetime] = None
    send_to_email: bool = False
