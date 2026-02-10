import uuid
from datetime import datetime
from sqlalchemy import Text, String, DateTime, Enum, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from enum import Enum as PyEnum

from .base import BaseDbModel

class ReceiptRequestStatus(PyEnum):
    pending = "pending"
    processed = "processed"
    rejected = "rejected"

class ReceiptRequest(BaseDbModel):
    __tablename__ = "receipt_requests"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    period: Mapped[str | None] = mapped_column(String(30), nullable=True)  # например "02.2026"
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[ReceiptRequestStatus] = mapped_column(
        Enum(ReceiptRequestStatus, name="receipt_request_status", native_enum=True),
        nullable=False,
        default=ReceiptRequestStatus.pending,
    )

    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    processed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    response_notification_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("notifications.id", ondelete="SET NULL"), nullable=True
    )
    send_to_email: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
