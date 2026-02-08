from pydantic import BaseModel, EmailStr, Field
from typing import Optional

class StudentCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=128)
    full_name: Optional[str] = None
    phone: Optional[str] = None
    is_active: bool = True
    room_id: Optional[str] = None  # если передали — сразу заселяем
