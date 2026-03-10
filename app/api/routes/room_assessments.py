from fastapi import APIRouter, Depends, HTTPException, Path, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, update, func
from ...core.database import get_db
from ...api.deps import get_current_user
from ...models.user import User
from ...models.room_assessment import RoomAssessment
from ...schemas.room_assessment import RoomAssessmentCreate, RoomAssessmentOut, MyRoomOut

# ЗАГЛУШКИ-импорты моделей комнаты/проживания – замени на свои, если имена другие:
from ...models.room import Room
from ...models.room_resident import RoomResident  # должен хранить user_id, room_id и is_active (или end_date is null)
from ...core.audit import audit_log

router = APIRouter(prefix="/rooms", tags=["rooms"])

def _ensure_admin(u: User):
    if u.role.value not in ("comendant", "head"):
        raise HTTPException(status_code=403, detail="Недостаточно прав")

@router.get("/by-number/{number}")
async def get_room_by_number(
    number: str = Path(...),
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
):
    # доступ для админов (комендант/зав)
    _ensure_admin(current)
    res = await db.execute(select(Room).where(Room.number == number))
    room = res.scalar_one_or_none()
    if not room:
        raise HTTPException(404, "Комната не найдена")
    return {"id": str(room.id), "number": room.number}

@router.get("/me", response_model=MyRoomOut)
async def my_room_info(
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
):
    # найти активную комнату пользователя
    res = await db.execute(
        select(RoomResident, Room)
        .join(Room, RoomResident.room_id == Room.id)
        .where((RoomResident.user_id == current.id) & (RoomResident.is_active == True))
        .limit(1)
    )
    row = res.first()
    if not row:
        raise HTTPException(404, "За вами не закреплена активная комната")
    rr, room = row

    # последняя оценка
    ra_q = await db.execute(
        select(RoomAssessment).where(RoomAssessment.room_id == room.id).order_by(desc(RoomAssessment.assessed_at)).limit(1)
    )
    ra = ra_q.scalar_one_or_none()

    assessed_by_name = None
    if ra:
        from ...models.user import User as AppUser
        u = await db.get(AppUser, ra.assessed_by)
        assessed_by_name = getattr(u, "full_name", None) or getattr(u, "email", None)

    return MyRoomOut(
        room_id=str(room.id),
        room_number=room.number,
        last_assessment=RoomAssessmentOut(
            score=ra.score,
            comment=ra.comment,
            assessed_at=ra.assessed_at,
            assessed_by_name=assessed_by_name,
        ) if ra else None
    )

@router.post("/{room_id}/assess", response_model=RoomAssessmentOut, status_code=201)
async def assess_room(
    room_id: str,
    payload: RoomAssessmentCreate,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
):
    _ensure_admin(current)
    # проверим, что комната существует
    room = await db.get(Room, room_id)
    if not room:
        raise HTTPException(404, "Комната не найдена")
    ra = RoomAssessment(room_id=room.id, score=payload.score, comment=payload.comment, assessed_by=current.id)
    db.add(ra)
    await db.commit()
    await db.refresh(ra)

    assessed_by_name = getattr(current, "full_name", None) or getattr(current, "email", None)
    audit_log("room_assessed", entity_type="room", entity_id=room_id, detail={"score": payload.score})
    return RoomAssessmentOut(score=ra.score, comment=ra.comment, assessed_at=ra.assessed_at, assessed_by_name=assessed_by_name)


@router.post("", status_code=201)
async def create_room(
    number: str = Body(..., embed=True),
    capacity: int | None = Body(None, embed=True),
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
):
    _ensure_admin(current)
    # уникальный номер
    exists = await db.execute(select(Room).where(Room.number == number))
    if exists.scalar_one_or_none():
        raise HTTPException(400, "Комната с таким номером уже существует")
    r = Room(number=number, capacity=capacity)
    db.add(r)
    await db.commit()
    audit_log("room_created", entity_type="room", entity_id=str(r.id), detail={"number": r.number})
    return {"id": str(r.id), "number": r.number}

@router.post("/{room_id}/assign", status_code=200)
async def assign_user_to_room(
    room_id: str,
    user_id: str = Body(..., embed=True),
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
):
    _ensure_admin(current)

    room = await db.get(Room, room_id)
    if not room:
        raise HTTPException(404, "Комната не найдена")

    # снимаем предыдущую активную привязку (если была)
    await db.execute(
        update(RoomResident)
        .where((RoomResident.user_id == user_id) & (RoomResident.is_active == True))
        .values(is_active=False)
    )

    rr = RoomResident(room_id=room.id, user_id=user_id, is_active=True)
    db.add(rr)
    await db.commit()
    audit_log("user_assigned_to_room", entity_type="room_resident", detail={"user_id": user_id, "room_id": room_id})
    return {"status": "ok"}

@router.post("/{room_id}/release", status_code=200)
async def release_user_from_room(
    room_id: str,
    user_id: str = Body(..., embed=True),
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
):
    _ensure_admin(current)
    # деактивируем активную запись (если есть)
    res = await db.execute(
        select(RoomResident)
        .where(
            (RoomResident.user_id == user_id) &
            (RoomResident.room_id == room_id) &
            (RoomResident.is_active == True)
        )
    )
    rr = res.scalar_one_or_none()
    if not rr:
        return {"status": "noop"}
    rr.is_active = False
    rr.released_at = func.now()
    await db.commit()
    audit_log("user_released_from_room", entity_type="room_resident", detail={"user_id": user_id, "room_id": room_id})
    return {"status": "ok"}