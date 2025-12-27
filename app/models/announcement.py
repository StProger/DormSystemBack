import uuid
from sqlalchemy import Text, ForeignKey, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseDbModel
from datetime import datetime

class Announcement(BaseDbModel):
    __tablename__ = "announcement"

    title: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    image_file_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("file_storage.id", ondelete="SET NULL"))
    publish_at: Mapped["datetime"] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())