import secrets, string
from datetime import datetime, timedelta, timezone
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Body, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_

from ...core.database import get_db
from ...api.deps import get_current_user
from ...models.user import User
from ...models.guest_pass import GuestPass, GuestPassStatus
from ...core.audit import audit_log
from ...schemas.guest_pass import (
    GuestPassCreate, GuestPassOut, GuestPassAdminOut, GuestPassAdminUpdate
)

router = APIRouter(prefix="/guest-passes", tags=["guest-passes"])

def _ensure_admin(u: User):
    if u.role.value not in ("comendant", "head"):
        raise HTTPException(status_code=403, detail="Недостаточно прав")

def _ensure_guard(u: User):
    if u.role.value not in ("guard", "comendant", "head"):
        raise HTTPException(status_code=403, detail="Недостаточно прав")

def _code(n: int = 8) -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alphabet) for _ in range(n))

# --- student
@router.post("", response_model=GuestPassOut, status_code=201)
async def create_guest_pass(
    payload: GuestPassCreate,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
):
    gp = GuestPass(
        resident_id=current.id,
        guest_full_name=payload.guest_full_name.strip(),
        guest_document=(payload.guest_document or None),
        note=(payload.note or None),
        planned_from=payload.planned_from,
        planned_to=payload.planned_to,
        status=GuestPassStatus.pending,
    )
    db.add(gp)
    await db.commit()
    await db.refresh(gp)
    audit_log("guest_pass_created", entity_type="guest_pass", entity_id=str(gp.id))
    return GuestPassOut(
        id=str(gp.id),
        guest_full_name=gp.guest_full_name,
        guest_document=gp.guest_document,
        note=gp.note,
        planned_from=gp.planned_from,
        planned_to=gp.planned_to,
        status=gp.status.value,
        code=gp.code,
        code_expires_at=gp.code_expires_at,
        checked_in_at=gp.checked_in_at,
        checked_out_at=gp.checked_out_at,
        created_at=gp.created_at,
    )

@router.get("/me", response_model=List[GuestPassOut])
async def list_my_guest_passes(
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
):
    res = await db.execute(select(GuestPass).where(GuestPass.resident_id == current.id).order_by(GuestPass.created_at.desc()))
    items = res.scalars().all()
    return [
        GuestPassOut(
            id=str(g.id),
            guest_full_name=g.guest_full_name,
            guest_document=g.guest_document,
            note=g.note,
            planned_from=g.planned_from,
            planned_to=g.planned_to,
            status=g.status.value,
            code=g.code,
            code_expires_at=g.code_expires_at,
            checked_in_at=g.checked_in_at,
            checked_out_at=g.checked_out_at,
            created_at=g.created_at,
        )
        for g in items
    ]

# --- admin
@router.get("", response_model=List[GuestPassAdminOut])
async def admin_list_guest_passes(
    status: Optional[str] = Query(None, description="pending,approved,rejected,checked_in,checked_out,expired"),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
):
    _ensure_admin(current)
    q = select(GuestPass).order_by(GuestPass.created_at.desc())
    conds = []
    if status:
        try:
            conds.append(GuestPass.status == GuestPassStatus(status))
        except Exception:
            raise HTTPException(400, "Unknown status")
    if date_from:
        conds.append(GuestPass.planned_from >= date_from)
    if date_to:
        conds.append(GuestPass.planned_from <= date_to)

    if conds:
        q = q.where(and_(*conds))
    res = await db.execute(q)
    items = res.scalars().all()

    # подтащим имена пользователей
    from ...models.user import User as AppUser
    user_ids = {str(i.resident_id) for i in items}
    user_ids.update({str(i.approved_by) for i in items if i.approved_by})
    users = {}
    if user_ids:
        r = await db.execute(select(AppUser).where(AppUser.id.in_(user_ids)))
        for u in r.scalars():
            users[str(u.id)] = u

    out = []
    for g in items:
        out.append(GuestPassAdminOut(
            id=str(g.id),
            resident_id=str(g.resident_id),
            resident_name=getattr(users.get(str(g.resident_id)), "full_name", None) or getattr(users.get(str(g.resident_id)), "email", None),
            guest_full_name=g.guest_full_name,
            guest_document=g.guest_document,
            note=g.note,
            planned_from=g.planned_from,
            planned_to=g.planned_to,
            status=g.status.value,
            code=g.code,
            code_expires_at=g.code_expires_at,
            checked_in_at=g.checked_in_at,
            checked_out_at=g.checked_out_at,
            approved_by=(getattr(users.get(str(g.approved_by)), "full_name", None) if g.approved_by else None),
            created_at=g.created_at,
        ))
    return out

@router.patch("/{gp_id}", response_model=GuestPassAdminOut)
async def admin_update_guest_pass(
    gp_id: str,
    payload: GuestPassAdminUpdate,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
):
    _ensure_admin(current)
    g = await db.get(GuestPass, gp_id)
    if not g:
        raise HTTPException(404, "Запрос не найден")

    if payload.action == "approve":
        g.status = GuestPassStatus.approved
        g.approved_by = current.id
        if not g.code:
            g.code = _code(8)
        if not g.code_expires_at:
            # если есть planned_to — используем, иначе сутки от planned_from
            base = g.planned_to or (g.planned_from + timedelta(days=1))
            g.code_expires_at = base
        audit_log("guest_pass_approved", entity_type="guest_pass", entity_id=str(g.id))
    elif payload.action == "reject":
        g.status = GuestPassStatus.rejected
        g.approved_by = current.id
        g.code = None
        g.code_expires_at = None
        audit_log("guest_pass_rejected", entity_type="guest_pass", entity_id=str(g.id))

    await db.commit()
    await db.refresh(g)

    resident_name = None
    approver_name = None
    from ...models.user import User as AppUser
    r = await db.get(AppUser, g.resident_id)
    a = await db.get(AppUser, g.approved_by) if g.approved_by else None
    if r: resident_name = getattr(r, "full_name", None) or getattr(r, "email", None)
    if a: approver_name = getattr(a, "full_name", None) or getattr(a, "email", None)

    return GuestPassAdminOut(
        id=str(g.id),
        resident_id=str(g.resident_id),
        resident_name=resident_name,
        guest_full_name=g.guest_full_name,
        guest_document=g.guest_document,
        note=g.note,
        planned_from=g.planned_from,
        planned_to=g.planned_to,
        status=g.status.value,
        code=g.code,
        code_expires_at=g.code_expires_at,
        checked_in_at=g.checked_in_at,
        checked_out_at=g.checked_out_at,
        approved_by=approver_name,
        created_at=g.created_at,
    )

# --- guard
@router.post("/check-in")
async def guard_check_in(
    code: str = Body(..., embed=True),
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
):
    _ensure_guard(current)
    now = datetime.now(timezone.utc)
    res = await db.execute(select(GuestPass).where(GuestPass.code == code))
    g = res.scalar_one_or_none()
    if not g:
        raise HTTPException(404, "Код не найден")
    if g.status not in (GuestPassStatus.approved,):
        raise HTTPException(400, f"Нельзя выполнить вход из статуса {g.status.value}")
    if g.code_expires_at and now > g.code_expires_at:
        g.status = GuestPassStatus.expired
        await db.commit()
        raise HTTPException(400, "Срок действия кода истёк")
    g.status = GuestPassStatus.checked_in
    g.checked_in_at = now
    await db.commit()
    audit_log("guest_check_in", entity_type="guest_pass", entity_id=str(g.id))
    return {"status": "ok", "id": str(g.id)}

@router.post("/check-out")
async def guard_check_out(
    code: str = Body(..., embed=True),
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
):
    _ensure_guard(current)
    now = datetime.now(timezone.utc)
    res = await db.execute(select(GuestPass).where(GuestPass.code == code))
    g = res.scalar_one_or_none()
    if not g:
        raise HTTPException(404, "Код не найден")
    if g.status not in (GuestPassStatus.checked_in,):
        raise HTTPException(400, f"Нельзя выполнить выход из статуса {g.status.value}")
    g.status = GuestPassStatus.checked_out
    g.checked_out_at = now
    await db.commit()
    audit_log("guest_check_out", entity_type="guest_pass", entity_id=str(g.id))
    return {"status": "ok", "id": str(g.id)}
