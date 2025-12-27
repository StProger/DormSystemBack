import uuid
from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseDbModel

class TicketAttachment(BaseDbModel):
    __tablename__ = "ticket_attachment"

    ticket_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ticket.id", ondelete="CASCADE"), nullable=False)
    file_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("file_storage.id", ondelete="CASCADE"), nullable=False)
