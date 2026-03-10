from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update, delete
from datetime import datetime, timezone
import re
from passlib.context import CryptContext

from ...models.user import UserRole
from ...schemas.admin_students import StudentCreate
from ...models.room_resident import RoomResident
from ...core.database import get_db
from ..deps import get_current_user
from ...models.user import User, UserRole
from ...models.room import Room
from ...models.room_resident import RoomResident
from ...core.audit import audit_log
from ...schemas.admin_rooms import (
    RoomCreate, RoomAdminOut, StudentAdminOut,
    AssignRequest, ReleaseRequest
)

router = APIRouter(prefix="/admin", tags=["admin"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
_email_re = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

def _ensure_head(u: User):
    # подстрой под свою модель роли (enum/string)
    role = getattr(u, "role", None)
    role_val = getattr(role, "value", role)
    if role_val != "head":
        raise HTTPException(status_code=403, detail="Только заведующий может выполнять это действие")

# -------- Rooms --------

@router.get("/rooms", response_model=list[RoomAdminOut])
async def list_rooms(
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
):
    _ensure_head(current)

    # загрузка по комнатам (count активных проживаний)
    q = (
        select(
            Room,
            func.count(RoomResident.id).label("occ"),
        )
        .outerjoin(RoomResident, (RoomResident.room_id == Room.id) & (RoomResident.is_active == True))
        .group_by(Room.id)
        .order_by(Room.number.asc())
    )
    res = await db.execute(q)
    rows = res.all()

    return [
        RoomAdminOut(
            id=str(room.id),
            number=room.number,
            capacity=room.capacity,
            occupancy=int(occ),
        )
        for room, occ in rows
    ]

@router.post("/rooms", response_model=RoomAdminOut, status_code=201)
async def create_room(
    payload: RoomCreate,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
):
    _ensure_head(current)

    number = payload.number.strip()
    exists = await db.execute(select(Room).where(Room.number == number))
    if exists.scalar_one_or_none():
        raise HTTPException(400, "Комната с таким номером уже существует")

    room = Room(number=number, capacity=payload.capacity)
    db.add(room)
    await db.commit()
    await db.refresh(room)

    audit_log("room_created", entity_type="room", entity_id=str(room.id), detail={"number": room.number})
    return RoomAdminOut(id=str(room.id), number=room.number, capacity=room.capacity, occupancy=0)

@router.delete("/rooms/{room_id}", status_code=204)
async def delete_room(
    room_id: str,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
):
    _ensure_head(current)

    # запрещаем удаление, если кто-то проживает
    occ_res = await db.execute(
        select(func.count(RoomResident.id)).where((RoomResident.room_id == room_id) & (RoomResident.is_active == True))
    )
    occ = int(occ_res.scalar() or 0)
    if occ > 0:
        raise HTTPException(400, "Нельзя удалить комнату: в ней есть проживающие")

    r = await db.get(Room, room_id)
    if not r:
        raise HTTPException(404, "Комната не найдена")

    await db.delete(r)
    await db.commit()
    audit_log("room_deleted", entity_type="room", entity_id=room_id, detail={"number": r.number})
    return None

# -------- Users search --------

@router.get("/students", response_model=list[StudentAdminOut])
async def search_students(
    query: str = Query("", description="Поиск по ФИО или email"),
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
):
    _ensure_head(current)

    q = query.strip().lower()

    # выбираем студентов (role = student) + их текущую комнату (если есть)
    # subquery активного проживания
    rr = RoomResident
    sub = (
        select(rr.user_id, rr.room_id)
        .where(rr.is_active == True)
        .subquery()
    )

    # join users + active room
    role = getattr(User, "role")
    role_val = UserRole.student

    stmt = (
        select(User, Room)
        .outerjoin(sub, sub.c.user_id == User.id)
        .outerjoin(Room, Room.id == sub.c.room_id)
        .where(role == role_val)
        .order_by(User.id.desc())
        .limit(limit)
    )

    if q:
        # если у тебя поле ФИО называется иначе — поменяй тут
        full_name_col = getattr(User, "full_name", None)
        email_col = getattr(User, "email", None)

        conds = []
        if full_name_col is not None:
            conds.append(func.lower(full_name_col).contains(q))
        if email_col is not None:
            conds.append(func.lower(email_col).contains(q))
        if conds:
            stmt = stmt.where(func.coalesce(*conds) if len(conds) == 1 else (conds[0] | conds[1]))

    res = await db.execute(stmt)
    rows = res.all()

    out = []
    for u, room in rows:
        out.append(StudentAdminOut(
            id=str(u.id),
            full_name=getattr(u, "full_name", None),
            email=getattr(u, "email", None),
            current_room_id=str(room.id) if room else None,
            current_room_number=room.number if room else None,
        ))
    return out

@router.post("/students", response_model=StudentAdminOut, status_code=201)
async def create_student(
    payload: StudentCreate,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
):
    _ensure_head(current)

    email = payload.email.strip().lower()
    if not _email_re.match(email):
        raise HTTPException(400, "Некорректный email")

    # проверка уникальности
    res = await db.execute(select(User).where(User.email == email))
    if res.scalar_one_or_none():
        raise HTTPException(400, "Пользователь с таким email уже существует")

    # если сразу заселяем — проверим комнату и capacity
    room = None
    if payload.room_id:
        room = await db.get(Room, payload.room_id)
        if not room:
            raise HTTPException(404, "Комната не найдена")

        if room.capacity is not None:
            occ_res = await db.execute(
                select(func.count(RoomResident.id)).where(
                    (RoomResident.room_id == room.id) & (RoomResident.is_active == True)
                )
            )
            occ = int(occ_res.scalar() or 0)
            if occ >= int(room.capacity):
                raise HTTPException(400, "В комнате нет свободных мест (capacity)")

    # создаём пользователя
    u = User(
        email=email,
        password_hash=pwd_context.hash(payload.password),
        role=UserRole.student,
        full_name=(payload.full_name.strip() if payload.full_name else None),
        phone=(payload.phone.strip() if payload.phone else None),
        is_active=payload.is_active,
    )
    db.add(u)
    await db.flush()  # получаем u.id без commit

    # если указали комнату — заселяем
    current_room_id = None
    current_room_number = None
    if room:
        rr = RoomResident(user_id=u.id, room_id=room.id, is_active=True)
        db.add(rr)
        current_room_id = str(room.id)
        current_room_number = room.number

    await db.commit()
    await db.refresh(u)

    audit_log("student_created", entity_type="user", entity_id=str(u.id), detail={"email": email})
    return StudentAdminOut(
        id=str(u.id),
        full_name=u.full_name,
        email=u.email,
        current_room_id=current_room_id,
        current_room_number=current_room_number,
    )


# -------- Occupancy: settle/transfer/evict --------

@router.post("/occupancy/assign", status_code=200)
async def assign_student_to_room(
    payload: AssignRequest,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
):
    _ensure_head(current)

    room = await db.get(Room, payload.room_id)
    if not room:
        raise HTTPException(404, "Комната не найдена")

    # capacity check (если задана)
    if room.capacity is not None:
        occ_res = await db.execute(
            select(func.count(RoomResident.id)).where((RoomResident.room_id == room.id) & (RoomResident.is_active == True))
        )
        occ = int(occ_res.scalar() or 0)
        if occ >= int(room.capacity):
            raise HTTPException(400, "В комнате нет свободных мест (capacity)")

    now = datetime.now(timezone.utc)

    # деактивируем текущую активную комнату студента (если была)
    await db.execute(
        update(RoomResident)
        .where((RoomResident.user_id == payload.user_id) & (RoomResident.is_active == True))
        .values(is_active=False, released_at=now)
    )

    # создаём новую активную запись
    rr = RoomResident(user_id=payload.user_id, room_id=room.id, is_active=True)
    db.add(rr)
    await db.commit()
    audit_log("student_assigned_to_room", entity_type="room_resident", detail={"user_id": str(payload.user_id), "room_id": str(room.id)})

    return {"status": "ok"}

@router.post("/occupancy/release", status_code=200)
async def release_student(
    payload: ReleaseRequest,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
):
    _ensure_head(current)

    now = datetime.now(timezone.utc)
    res = await db.execute(
        select(RoomResident)
        .where((RoomResident.user_id == payload.user_id) & (RoomResident.is_active == True))
        .limit(1)
    )
    rr = res.scalar_one_or_none()
    if not rr:
        return {"status": "noop"}

    rr.is_active = False
    rr.released_at = now
    await db.commit()
    audit_log("student_released_from_room", entity_type="room_resident", detail={"user_id": str(payload.user_id)})
    return {"status": "ok"}
