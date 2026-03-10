import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.database import get_db
from ..deps import get_current_user
from ...models.user import User
from ...schemas.notifications import NotificationListItem, NotificationDetailOut, NotificationAttachmentOut, UnreadCountOut
from ...services.notifications_service import (
    get_user_notifications_list, get_user_notification_detail, mark_read, unread_count
)
from ...core.storage_minio import presign_get
from ...core.audit import audit_log

router = APIRouter(prefix="/notifications", tags=["notifications"])

@router.get("", response_model=list[NotificationListItem])
async def list_my_notifications(
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
):
    rows = await get_user_notifications_list(db, current.id, limit=50)
    out = []
    for n, r in rows:
        body = (n.body or "").strip()
        preview = body[:120] + ("…" if len(body) > 120 else "")
        out.append(NotificationListItem(
            id=str(n.id),
            title=n.title,
            created_at=n.created_at,
            is_read=r.is_read,
            read_at=r.read_at,
            preview=preview,
        ))
    return out

@router.get("/unread-count", response_model=UnreadCountOut)
async def my_unread_count(
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
):
    return UnreadCountOut(unread=await unread_count(db, current.id))

@router.get("/{notification_id}", response_model=NotificationDetailOut)
async def get_my_notification(
    notification_id: str,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
):
    nid = uuid.UUID(notification_id)
    notif, rec, atts = await get_user_notification_detail(db, current.id, nid)
    if not notif:
        raise HTTPException(404, "Уведомление не найдено")

    attachments = []
    for a in atts:
        attachments.append(NotificationAttachmentOut(
            id=str(a.id),
            filename=a.filename,
            content_type=a.content_type,
            size_bytes=a.size_bytes,
            download_url=presign_get(a.s3_key, expire_minutes=10),
        ))

    return NotificationDetailOut(
        id=str(notif.id),
        title=notif.title,
        body=notif.body,
        created_at=notif.created_at,
        is_read=rec.is_read,
        read_at=rec.read_at,
        attachments=attachments,
    )

@router.post("/{notification_id}/read")
async def mark_my_notification_read(
    notification_id: str,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
):
    nid = uuid.UUID(notification_id)
    await mark_read(db, current.id, nid)
    await db.commit()
    audit_log("notification_read", entity_type="notification", entity_id=notification_id)
    return {"status": "ok"}
