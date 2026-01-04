import uuid
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Text, SmallInteger
from app.models.base import BaseDbModel

class Room(BaseDbModel):
    __tablename__ = "room"

    # Номер комнаты уникален в рамках общежития (одно общежитие в системе)
    number: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    # capacity опционально (можно не заполнять)
    capacity: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
