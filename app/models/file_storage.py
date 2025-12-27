import uuid
from sqlalchemy import String, Text, Boolean, BigInteger, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseDbModel
from enum import Enum as PyEnum

class StorageBackend(PyEnum):
    s3 = "s3"

class FileStorage(BaseDbModel):
    __tablename__ = "file_storage"

    backend: Mapped[StorageBackend] = mapped_column(Enum(StorageBackend, name="storage_backend", native_enum=True), default=StorageBackend.s3, nullable=False)
    bucket: Mapped[str] = mapped_column(Text, nullable=False)
    object_key: Mapped[str] = mapped_column(Text, nullable=False)
    file_name: Mapped[str] = mapped_column(Text, nullable=False)
    mime_type: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    etag: Mapped[str | None] = mapped_column(Text)
    sha256: Mapped[str | None] = mapped_column(String(64))
    uploaded_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)  # FK опустим в ORM, проверим на уровне бизнес-логики
    uploaded_at: Mapped[str] = mapped_column(Text, nullable=False, default="now()")    # упростим; реально лучше timestamptz
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
