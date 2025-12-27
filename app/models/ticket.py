import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import Text, DateTime, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import BaseDbModel

class TicketType(PyEnum):
    repair = "repair"
    maintenance = "maintenance"
    receipt = "receipt"
    large_item = "large_item"

class TicketStatus(PyEnum):
    in_processing = "in_processing"
    in_work = "in_work"
    done = "done"

class Ticket(BaseDbModel):
    __tablename__ = "ticket"

    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[TicketType] = mapped_column(Enum(TicketType, name="ticket_type", native_enum=True), nullable=False)
    status: Mapped[TicketStatus] = mapped_column(Enum(TicketStatus, name="ticket_status", native_enum=True), nullable=False, default=TicketStatus.in_processing)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    admin_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
