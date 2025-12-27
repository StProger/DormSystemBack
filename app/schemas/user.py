from uuid import UUID

from pydantic import BaseModel, EmailStr
from enum import Enum

class UserRole(str, Enum):
    student = "student"
    comendant = "comendant"
    head = "head"
    guard = "guard"

class UserOut(BaseModel):
    id: str | UUID
    email: EmailStr
    role: UserRole
    full_name: str | None = None
    phone: str | None = None

    class Config:
        from_attributes = True
