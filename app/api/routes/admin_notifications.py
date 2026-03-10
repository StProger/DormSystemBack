import json
import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ...core.database import get_db
from ..deps import get_current_user
from ...models.user import User, UserRole
from ...models.room_resident import RoomResident
from ...schemas.notifications import NotificationDetailOut
from ...core.audit import audit_log
from ...services.notifications_service import create_notification

router = APIRouter(prefix="/admin/notifications", tags=["admin-notifications"])

def _ensure_admin(u: User):
    if u.role not in (UserRole.head, UserRole.comendant):
        raise HTTPException(403, "Недостаточно прав")

@router.post("")
async def admin_send_notification(
    title: str = Form(...),
    body: str = Form(...),
    recipient_ids_json: str = Form(..., description='JSON список user_id: ["...","..."]'),
    files: list[UploadFile] = File(default_factory=list),
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
):
    _ensure_admin(current)

    try:
        ids = json.loads(recipient_ids_json)
        recipient_ids = [uuid.UUID(x) for x in ids]
    except Exception:
        raise HTTPException(400, "recipient_ids_json должен быть JSON списком UUID")

    nid = await create_notification(
        db,
        title=title.strip(),
        body=body.strip(),
        created_by_user_id=current.id,
        recipient_user_ids=recipient_ids,
        files=files or None,
    )
    await db.commit()
    audit_log("notification_sent", entity_type="notification", entity_id=str(nid), detail={"recipients": len(recipient_ids)})
    return {"status": "ok", "notification_id": str(nid)}
