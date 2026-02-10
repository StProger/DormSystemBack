import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from ...core.database import get_db
from ..deps import get_current_user
from ...models.user import User, UserRole
from ...models.receipt_request import ReceiptRequest, ReceiptRequestStatus
from ...schemas.receipt_requests import ReceiptRequestCreate, ReceiptRequestOut
from ...services.notifications_service import create_notification
from ...models.user import User
from ...models.notification import NotificationAttachment
from ...core.storage_minio import presign_get
from ...core.email_smtp import send_email_html
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/receipt-requests", tags=["receipt-requests"])

@router.post("", response_model=ReceiptRequestOut, status_code=201)
async def create_receipt_request(
    payload: ReceiptRequestCreate,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
):
    if current.role != UserRole.student:
        raise HTTPException(403, "Только студент может создавать запрос квитанции")

    req = ReceiptRequest(
        user_id=current.id,
        period=payload.period,
        comment=payload.comment,
        status=ReceiptRequestStatus.pending,
        send_to_email=payload.send_to_email,
    )
    db.add(req)
    await db.commit()
    await db.refresh(req)

    return ReceiptRequestOut(
        id=str(req.id),
        period=req.period,
        comment=req.comment,
        status=req.status.value,
        created_at=req.created_at,
        processed_at=req.processed_at,
        send_to_email=payload.send_to_email,
    )

@router.get("", response_model=list[ReceiptRequestOut])
async def list_my_receipt_requests(
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
):
    stmt = select(ReceiptRequest).where(ReceiptRequest.user_id == current.id).order_by(ReceiptRequest.created_at.desc())
    res = await db.execute(stmt)
    items = res.scalars().all()
    return [
        ReceiptRequestOut(
            id=str(x.id),
            period=x.period,
            comment=x.comment,
            status=x.status.value,
            created_at=x.created_at,
            processed_at=x.processed_at,
            send_to_email=x.send_to_email,
        )
        for x in items
    ]


# ------- admin part -------
@router.get("/admin", response_model=list[ReceiptRequestOut])
async def admin_list_receipt_requests(
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
):
    if current.role not in (UserRole.head, UserRole.comendant):
        raise HTTPException(403)

    stmt = select(ReceiptRequest).order_by(ReceiptRequest.created_at.desc())
    if status:
        try:
            st = ReceiptRequestStatus(status)
        except Exception:
            raise HTTPException(400, "Неверный статус")
        stmt = stmt.where(ReceiptRequest.status == st)

    res = await db.execute(stmt)
    items = res.scalars().all()
    return [
        ReceiptRequestOut(
            id=str(x.id),
            period=x.period,
            comment=x.comment,
            status=x.status.value,
            created_at=x.created_at,
            processed_at=x.processed_at,
            send_to_email=x.send_to_email,
        )
        for x in items
    ]


@router.post("/admin/{request_id}/respond")
async def admin_respond_receipt_request(
    request_id: str,
    title: str = Form("Квитанция на оплату"),
    body: str = Form("Квитанция подготовлена. Файл во вложении."),
    files: list[UploadFile] = File(default_factory=list),
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
):
    if current.role not in (UserRole.head, UserRole.comendant):
        raise HTTPException(403)

    rid = uuid.UUID(request_id)
    req_res = await db.execute(select(ReceiptRequest).where(ReceiptRequest.id == rid))
    req = req_res.scalar_one_or_none()
    if not req:
        raise HTTPException(404, "Запрос не найден")
    if req.status != ReceiptRequestStatus.pending:
        raise HTTPException(400, "Запрос уже обработан")

    # создаём уведомление студенту
    nid = await create_notification(
        db,
        title=title.strip(),
        body=body.strip(),
        created_by_user_id=current.id,
        recipient_user_ids=[req.user_id],
        files=files or None,
    )

    now = datetime.now(timezone.utc)
    req.status = ReceiptRequestStatus.processed
    req.processed_at = now
    req.processed_by_user_id = current.id
    req.response_notification_id = nid

    await db.commit()
    # Дублирование на email (если запрошено)
    if req.send_to_email:
        try:
            ures = await db.execute(select(User).where(User.id == req.user_id))
            student = ures.scalar_one_or_none()
            if student and student.email:
                # заберём вложения уведомления и сделаем ссылки
                ares = await db.execute(
                    select(NotificationAttachment).where(NotificationAttachment.notification_id == nid)
                )
                atts = ares.scalars().all()
                links = []
                for a in atts:
                    links.append(f'<li><a href="{presign_get(a.s3_key, expire_minutes=60)}">{a.filename}</a></li>')

                links_html = "<ul>" + "".join(links) + "</ul>" if links else "<p>Вложений нет.</p>"

                html = f"""
                    <html>
                      <body>
                        <p>Здравствуйте!</p>
                        <p>По вашему запросу подготовлена квитанция.</p>
                        <p><b>{title}</b></p>
                        <p>{body}</p>
                        <p>Ссылки на файлы (действуют ограниченное время):</p>
                        {links_html}
                      </body>
                    </html>
                    """
                send_email_html(student.email, title, html)
        except Exception as e:
            logger.exception("Failed to send receipt email: %s", e)
    return {"status": "ok", "notification_id": str(nid)}
