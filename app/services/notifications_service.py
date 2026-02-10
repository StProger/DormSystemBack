import json
import uuid
from datetime import datetime, timezone
from typing import Iterable, Optional, List
from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func
from sqlalchemy.orm import aliased

from ..models.notification import Notification, NotificationRecipient, NotificationAttachment
from ..models.user import User, UserRole
from ..models.room_resident import RoomResident
from ..core.storage_minio import upload_file, presign_get

async def create_notification(
    db: AsyncSession,
    *,
    title: str,
    body: str,
    created_by_user_id: uuid.UUID | None,
    recipient_user_ids: list[uuid.UUID],
    files: list[UploadFile] | None = None,
) -> uuid.UUID:
    n = Notification(title=title, body=body, created_by_user_id=created_by_user_id)
    db.add(n)
    await db.flush()  # получаем n.id

    # recipients
    for uid in set(recipient_user_ids):
        db.add(NotificationRecipient(notification_id=n.id, user_id=uid, is_read=False))

    # attachments
    if files:
        for f in files:
            key, size, _etag = upload_file("notifications", f)
            att = NotificationAttachment(
                notification_id=n.id,
                s3_key=key,
                filename=f.filename or "file",
                content_type=f.content_type,
                size_bytes=size,
            )
            db.add(att)

    return n.id

async def get_user_notifications_list(db: AsyncSession, user_id: uuid.UUID, limit: int = 50):
    # join notifications + recipient status
    stmt = (
        select(Notification, NotificationRecipient)
        .join(NotificationRecipient, NotificationRecipient.notification_id == Notification.id)
        .where(NotificationRecipient.user_id == user_id)
        .order_by(Notification.created_at.desc())
        .limit(limit)
    )
    res = await db.execute(stmt)
    return res.all()

async def get_user_notification_detail(db: AsyncSession, user_id: uuid.UUID, notification_id: uuid.UUID):
    # recipient row
    r = await db.execute(
        select(NotificationRecipient).where(
            (NotificationRecipient.user_id == user_id) & (NotificationRecipient.notification_id == notification_id)
        )
    )
    rec = r.scalar_one_or_none()
    if not rec:
        return None, None, []

    nres = await db.execute(select(Notification).where(Notification.id == notification_id))
    notif = nres.scalar_one()

    ares = await db.execute(select(NotificationAttachment).where(NotificationAttachment.notification_id == notification_id))
    atts = ares.scalars().all()

    return notif, rec, atts

async def mark_read(db: AsyncSession, user_id: uuid.UUID, notification_id: uuid.UUID):
    now = datetime.now(timezone.utc)
    await db.execute(
        update(NotificationRecipient)
        .where(
            (NotificationRecipient.user_id == user_id)
            & (NotificationRecipient.notification_id == notification_id)
            & (NotificationRecipient.is_read == False)
        )
        .values(is_read=True, read_at=now)
    )

async def unread_count(db: AsyncSession, user_id: uuid.UUID) -> int:
    res = await db.execute(
        select(func.count(NotificationRecipient.id))
        .where((NotificationRecipient.user_id == user_id) & (NotificationRecipient.is_read == False))
    )
    return int(res.scalar() or 0)
