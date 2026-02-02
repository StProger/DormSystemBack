from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime

GuestPassStatus = Literal["pending","approved","rejected","checked_in","checked_out","expired"]

class GuestPassCreate(BaseModel):
    guest_full_name: str
    guest_document: Optional[str] = None
    note: Optional[str] = None
    planned_from: datetime
    planned_to: Optional[datetime] = None

class GuestPassOut(BaseModel):
    id: str
    guest_full_name: str
    guest_document: Optional[str] = None
    note: Optional[str] = None
    planned_from: datetime
    planned_to: Optional[datetime] = None
    status: GuestPassStatus
    code: Optional[str] = None
    code_expires_at: Optional[datetime] = None
    checked_in_at: Optional[datetime] = None
    checked_out_at: Optional[datetime] = None
    created_at: datetime

class GuestPassAdminOut(GuestPassOut):
    resident_id: str
    resident_name: Optional[str] = None
    approved_by: Optional[str] = None

class GuestPassAdminUpdate(BaseModel):
    action: Literal["approve","reject"]  # можно расширить
