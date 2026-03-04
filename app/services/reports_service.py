from __future__ import annotations
from datetime import date, datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from sqlalchemy.sql import text

from app.models.room import Room
from app.models.room_resident import RoomResident
from app.models.room_assessment import RoomAssessment

# ⚠️ поправь импорты под твои реальные файлы/модели:
from app.models.ticket import Ticket
from app.models.guest_pass import GuestPass


def _range_filter(col, from_date: date | None, to_date: date | None):
    conds = []
    if from_date:
        conds.append(col >= datetime.combine(from_date, datetime.min.time()))
    if to_date:
        # включительно до конца дня
        conds.append(col < datetime.combine(to_date + timedelta(days=1), datetime.min.time()))
    return and_(*conds) if conds else None


async def occupancy_report(db: AsyncSession) -> tuple[dict, list[dict]]:
    # summary counts
    rooms_total = int((await db.execute(select(func.count(Room.id)))).scalar() or 0)
    capacity_total = int((await db.execute(select(func.coalesce(func.sum(Room.capacity), 0)))).scalar() or 0)

    occupied_total = int((await db.execute(
        select(func.count(RoomResident.id)).where(RoomResident.is_active == True)
    )).scalar() or 0)

    free_total = max(capacity_total - occupied_total, 0)
    occupancy_rate = (occupied_total / capacity_total) if capacity_total else 0.0

    # per-room occupancy
    room_rows = (await db.execute(
        select(
            Room.id,
            Room.number,
            Room.capacity,
            func.count(RoomResident.id).filter(RoomResident.is_active == True).label("occupied"),
        )
        .outerjoin(RoomResident, RoomResident.room_id == Room.id)
        .group_by(Room.id)
        .order_by(Room.number.asc())
    )).all()

    # last rating per room
    last_rating_subq = (
        select(
            RoomAssessment.room_id.label("room_id"),
            func.max(RoomAssessment.created_at).label("max_created"),
        )
        .group_by(RoomAssessment.room_id)
        .subquery()
    )

    last_rating_rows = (await db.execute(
        select(RoomAssessment)
        .join(
            last_rating_subq,
            (RoomAssessment.room_id == last_rating_subq.c.room_id) &
            (RoomAssessment.created_at == last_rating_subq.c.max_created),
        )
    )).scalars().all()

    last_map = {str(r.room_id): r for r in last_rating_rows}

    rooms = []
    for rid, number, capacity, occupied in room_rows:
        rid_s = str(rid)
        lr = last_map.get(rid_s)
        cap = int(capacity or 0)
        occ = int(occupied or 0)
        rooms.append({
            "room_id": rid_s,
            "number": str(number),
            "capacity": cap,
            "occupied": occ,
            "free": max(cap - occ, 0),
            "last_rating": int(lr.score) if lr else None,
            "last_rating_comment": lr.comment if lr else None,
            "last_rating_at": lr.created_at.isoformat() if lr else None,
        })

    summary = {
        "rooms_total": rooms_total,
        "capacity_total": capacity_total,
        "occupied_total": occupied_total,
        "free_total": free_total,
        "occupancy_rate": occupancy_rate,
    }
    return summary, rooms


async def tickets_report(db: AsyncSession, from_date: date | None, to_date: date | None) -> tuple[list[dict], list[dict], list[dict]]:
    cond = _range_filter(Ticket.created_at, from_date, to_date)

    stmt_status = select(Ticket.status, func.count(Ticket.id)).group_by(Ticket.status)
    stmt_type = select(Ticket.type, func.count(Ticket.id)).group_by(Ticket.type)

    if cond is not None:
        stmt_status = stmt_status.where(cond)
        stmt_type = stmt_type.where(cond)

    by_status = [{"key": str(k), "count": int(c)} for k, c in (await db.execute(stmt_status)).all()]
    by_type = [{"key": str(k), "count": int(c)} for k, c in (await db.execute(stmt_type)).all()]

    # timeseries by day
    day_col = func.date_trunc("day", Ticket.created_at)
    stmt_day = select(day_col, func.count(Ticket.id)).group_by(day_col).order_by(day_col.asc())
    if cond is not None:
        stmt_day = stmt_day.where(cond)
    rows = (await db.execute(stmt_day)).all()

    by_day = []
    for d, c in rows:
        by_day.append({"day": d.date().isoformat(), "count": int(c)})

    return by_status, by_type, by_day


async def guest_pass_report(db: AsyncSession, from_date: date | None, to_date: date | None) -> tuple[list[dict], list[dict]]:
    cond = _range_filter(GuestPass.created_at, from_date, to_date)

    stmt_status = select(GuestPass.status, func.count(GuestPass.id)).group_by(GuestPass.status)
    if cond is not None:
        stmt_status = stmt_status.where(cond)
    by_status = [{"key": str(k), "count": int(c)} for k, c in (await db.execute(stmt_status)).all()]

    day_col = func.date_trunc("day", GuestPass.created_at)
    stmt_day = select(day_col, func.count(GuestPass.id)).group_by(day_col).order_by(day_col.asc())
    if cond is not None:
        stmt_day = stmt_day.where(cond)
    rows = (await db.execute(stmt_day)).all()

    by_day = [{"day": d.date().isoformat(), "count": int(c)} for d, c in rows]
    return by_status, by_day
