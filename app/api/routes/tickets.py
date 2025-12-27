from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.config import get_settings
from app.core.storage_minio import upload_file, presign_get
from app.models.user import User
from app.models.ticket import Ticket, TicketType, TicketStatus
from app.models.ticket_attachment import TicketAttachment
from app.models.file_storage import FileStorage, StorageBackend
from app.schemas.ticket import (
    TicketCreate, TicketOut, TicketAttachmentOut,
    TicketAdminOut, TicketAdminUpdate
)

router = APIRouter(prefix="/tickets", tags=["tickets"])
settings = get_settings()

@router.post("", response_model=TicketOut, status_code=201)
async def create_ticket(
    title: str = Form(...),
    description: str = Form(...),
    type: str = Form(...),  # "repair" | "maintenance" | "receipt"
    files: List[UploadFile] | None = File(None),
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
):
    # Разрешаем создавать заявки всем авторизованным (в первую очередь студентам)
    if type not in {"repair","maintenance","receipt","large_item"}:
        raise HTTPException(status_code=400, detail="Unknown ticket type")

    t = Ticket(
        title=title,
        description=description,
        type=TicketType(type),
        status=TicketStatus.in_processing,
        created_by=current.id,
    )
    db.add(t)
    await db.flush()

    # файлы (опционально)
    attachments: list[TicketAttachmentOut] = []
    if files:
        for f in files:
            key, size, etag = await upload_file("tickets", f)  # стриминг
            fs = FileStorage(
                backend=StorageBackend.s3,
                bucket=settings.S3_BUCKET,
                object_key=key,
                file_name=f.filename or "file",
                mime_type=f.content_type or "application/octet-stream",
                size_bytes=size or 0,
                etag=etag,
                uploaded_by=current.id,
                uploaded_at="now()",
            )
            db.add(fs)
            await db.flush()
            db.add(TicketAttachment(ticket_id=t.id, file_id=fs.id))
            attachments.append(TicketAttachmentOut(file_name=fs.file_name, url=presign_get(fs.object_key)))

    await db.commit()
    return TicketOut(
        id=str(t.id),
        title=t.title,
        description=t.description,
        type=t.type.value,
        status=t.status.value,
        created_at=t.created_at,
        attachments=attachments,
    )

@router.get("/me", response_model=list[TicketOut])
async def list_my_tickets(
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
):
    # мои заявки
    res = await db.execute(select(Ticket).where(Ticket.created_by == current.id).order_by(Ticket.created_at.desc()))
    tickets = res.scalars().all()
    if not tickets:
        return []

    # подтянем файлы одним запросом
    res2 = await db.execute(
        select(TicketAttachment, FileStorage)
        .join(FileStorage, TicketAttachment.file_id == FileStorage.id, isouter=True)
        .where(TicketAttachment.ticket_id.in_([t.id for t in tickets]))
    )
    attach_map: dict[str, list[TicketAttachmentOut]] = {}
    for ta, fs in res2:
        if not fs:
            continue
        url = presign_get(fs.object_key)
        attach_map.setdefault(str(ta.ticket_id), []).append(TicketAttachmentOut(file_name=fs.file_name, url=url))

    out: list[TicketOut] = []
    for t in tickets:
        out.append(TicketOut(
            id=str(t.id),
            title=t.title,
            description=t.description,
            type=t.type.value,
            status=t.status.value,
            created_at=t.created_at,
            attachments=attach_map.get(str(t.id), []),
        ))
    return out


def _ensure_admin(u: User):
    if u.role.value not in ("comendant", "head"):
        raise HTTPException(status_code=403, detail="Недостаточно прав")

@router.get("", response_model=list[TicketAdminOut])
async def admin_list_tickets(
    status: Optional[str] = Query(None, description="in_processing|in_work|done"),
    type: Optional[str] = Query(None, description="repair|maintenance|receipt|large_item"),
    only_unassigned: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
):
    _ensure_admin(current)

    conds = []
    if status:
        if status not in {"in_processing","in_work","done"}:
            raise HTTPException(400, "Unknown status")
        conds.append(Ticket.status == TicketStatus(status))
    if type:
        if type not in {"repair","maintenance","receipt","large_item"}:
            raise HTTPException(400, "Unknown type")
        conds.append(Ticket.type == TicketType(type))
    if only_unassigned:
        conds.append(Ticket.assigned_to.is_(None))

    stmt = select(Ticket).order_by(Ticket.created_at.desc())
    if conds:
        stmt = stmt.where(and_(*conds))
    res = await db.execute(stmt)
    tickets = res.scalars().all()

    if not tickets:
        return []

    # файлы для всех тикетов
    res2 = await db.execute(
        select(TicketAttachment, FileStorage)
        .join(FileStorage, TicketAttachment.file_id == FileStorage.id, isouter=True)
        .where(TicketAttachment.ticket_id.in_([t.id for t in tickets]))
    )
    attach_map: dict[str, list[TicketAttachmentOut]] = {}
    for ta, fs in res2:
        if not fs: continue
        url = presign_get(fs.object_key)
        attach_map.setdefault(str(ta.ticket_id), []).append(TicketAttachmentOut(file_name=fs.file_name, url=url))

    # пользователи (создатель и назначенный)
    user_ids = {str(t.created_by) for t in tickets}
    user_ids.update({str(t.assigned_to) for t in tickets if t.assigned_to})
    users_map = {}
    if user_ids:
        from ...models.user import User as AppUser
        res3 = await db.execute(select(AppUser).where(AppUser.id.in_(user_ids)))
        for u in res3.scalars():
            users_map[str(u.id)] = u

    out: list[TicketAdminOut] = []
    for t in tickets:
        c = users_map.get(str(t.created_by))
        a = users_map.get(str(t.assigned_to)) if t.assigned_to else None
        out.append(TicketAdminOut(
            id=str(t.id),
            title=t.title,
            description=t.description,
            type=t.type.value,
            status=t.status.value,
            created_at=t.created_at,
            updated_at=t.updated_at,
            closed_at=t.closed_at,
            created_by_id=str(t.created_by),
            created_by_email=getattr(c, "email", None),
            created_by_name=getattr(c, "full_name", None),
            assigned_to_id=str(t.assigned_to) if t.assigned_to else None,
            assigned_to_email=getattr(a, "email", None) if a else None,
            assigned_to_name=getattr(a, "full_name", None) if a else None,
            admin_comment=t.admin_comment,
            attachments=attach_map.get(str(t.id), []),
        ))
    return out

@router.patch("/{ticket_id}", response_model=TicketAdminOut)
async def admin_update_ticket(
    ticket_id: str,
    payload: TicketAdminUpdate,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
):
    _ensure_admin(current)

    t = await db.get(Ticket, ticket_id)
    if not t:
        raise HTTPException(404, "Заявка не найдена")

    # изменения
    if payload.assign_self:
        t.assigned_to = current.id

    if payload.status:
        t.status = TicketStatus(payload.status)
        if t.status == TicketStatus.done and not t.closed_at:
            t.closed_at = datetime.now(timezone.utc)
        if t.status != TicketStatus.done:
            t.closed_at = None

    if payload.admin_comment is not None:
        t.admin_comment = payload.admin_comment

    await db.commit()
    await db.refresh(t)

    # ответ аналогичен admin_list_tickets на один объект
    from ...models.user import User as AppUser
    users = {}
    res_u = await db.execute(select(AppUser).where(AppUser.id.in_([t.created_by] + ([t.assigned_to] if t.assigned_to else []))))
    for u in res_u.scalars():
        users[str(u.id)] = u

    res2 = await db.execute(
        select(TicketAttachment, FileStorage)
        .join(FileStorage, TicketAttachment.file_id == FileStorage.id, isouter=True)
        .where(TicketAttachment.ticket_id == t.id)
    )
    attachments = []
    for ta, fs in res2:
        if not fs: continue
        attachments.append(TicketAttachmentOut(file_name=fs.file_name, url=presign_get(fs.object_key)))

    c = users.get(str(t.created_by))
    a = users.get(str(t.assigned_to)) if t.assigned_to else None
    return TicketAdminOut(
        id=str(t.id),
        title=t.title,
        description=t.description,
        type=t.type.value,
        status=t.status.value,
        created_at=t.created_at,
        updated_at=t.updated_at,
        closed_at=t.closed_at,
        created_by_id=str(t.created_by),
        created_by_email=getattr(c, "email", None),
        created_by_name=getattr(c, "full_name", None),
        assigned_to_id=str(t.assigned_to) if t.assigned_to else None,
        assigned_to_email=getattr(a, "email", None) if a else None,
        assigned_to_name=getattr(a, "full_name", None) if a else None,
        admin_comment=t.admin_comment,
        attachments=attachments,
    )