from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class RoomAssessmentCreate(BaseModel):
    score: int = Field(ge=1, le=5)
    comment: Optional[str] = None

class RoomAssessmentOut(BaseModel):
    score: int
    comment: Optional[str] = None
    assessed_at: datetime
    assessed_by_name: Optional[str] = None

class MyRoomOut(BaseModel):
    room_id: str
    room_number: str
    last_assessment: Optional[RoomAssessmentOut] = None
