from pydantic import BaseModel, Field
from typing import Optional

class RoomCreate(BaseModel):
    number: str = Field(..., min_length=1)
    capacity: Optional[int] = Field(None, ge=1, le=20)

class RoomAdminOut(BaseModel):
    id: str
    number: str
    capacity: Optional[int] = None
    occupancy: int

class StudentAdminOut(BaseModel):
    id: str
    full_name: Optional[str] = None
    email: Optional[str] = None
    current_room_id: Optional[str] = None
    current_room_number: Optional[str] = None

class AssignRequest(BaseModel):
    user_id: str
    room_id: str

class ReleaseRequest(BaseModel):
    user_id: str
