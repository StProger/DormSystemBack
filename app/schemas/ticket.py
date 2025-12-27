from pydantic import BaseModel
from typing import Literal, List, Optional
from datetime import datetime

TicketType = Literal["repair","maintenance","receipt","large_item"]
TicketStatus = Literal["in_processing","in_work","done"]

class TicketCreate(BaseModel):
    title: str
    description: str
    type: TicketType

class TicketAttachmentOut(BaseModel):
    file_name: str
    url: str

class TicketOut(BaseModel):
    id: str
    title: str
    description: str
    type: TicketType
    status: TicketStatus
    created_at: datetime
    attachments: List[TicketAttachmentOut] = []

class TicketAdminUpdate(BaseModel):
    status: Optional[TicketStatus] = None
    assign_self: Optional[bool] = None
    admin_comment: Optional[str] = None

class TicketAdminOut(BaseModel):
    id: str
    title: str
    description: str
    type: TicketType
    status: TicketStatus
    created_at: datetime
    updated_at: datetime
    closed_at: Optional[datetime] = None
    created_by_id: str
    created_by_email: Optional[str] = None
    created_by_name: Optional[str] = None
    assigned_to_id: Optional[str] = None
    assigned_to_email: Optional[str] = None
    assigned_to_name: Optional[str] = None
    admin_comment: Optional[str] = None
    attachments: List[TicketAttachmentOut] = []
