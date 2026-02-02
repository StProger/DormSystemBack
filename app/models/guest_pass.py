import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import Text, DateTime, Enum, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import BaseDbModel

class GuestPassStatus(PyEnum):
    pending = "pending"         # создано студентом, ждёт решения
    approved = "approved"       # одобрено, код выдан
    rejected = "rejected"       # отклонено админом
    checked_in = "checked_in"   # гость прошёл внутрь
    checked_out = "checked_out" # гость вышел
    expired = "expired"         # истёк срок действия кода

class GuestPass(BaseDbModel):
    __tablename__ = "guest_pass"


    # кто приглашает (проживающий)
    resident_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    guest_full_name: Mapped[str] = mapped_column(Text, nullable=False)
    guest_document: Mapped[str | None] = mapped_column(Text, nullable=True)  # серия/номер, документ
    note: Mapped[str | None] = mapped_column(Text, nullable=True)            # цель визита / комментарий

    planned_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    planned_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    status: Mapped[GuestPassStatus] = mapped_column(
        Enum(GuestPassStatus, name="guest_pass_status", native_enum=True),
        default=GuestPassStatus.pending, nullable=False
    )

    # Код для поста охраны (покажем студенту после одобрения)
    code: Mapped[str | None] = mapped_column(Text, nullable=True, unique=True)
    code_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    approved_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    checked_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    checked_out_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("code", name="uq_guest_pass_code"),
    )
