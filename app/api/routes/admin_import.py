from __future__ import annotations

import re
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from passlib.context import CryptContext

from ...core.database import get_db
from ..deps import get_current_user
from ...models.user import User, UserRole  # <-- ВАЖНО: импортируем UserRole
from ...models.room import Room
from ...core.excel import read_sheet_rows_xlsx, ExcelError
from ...core.audit import audit_log
from ...schemas.import_result import ImportResult, ImportRowError

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

router = APIRouter(prefix="/admin/import", tags=["admin-import"])

def _ensure_head(u: User):
    # role у тебя Enum(UserRole)
    if u.role != UserRole.head:
        raise HTTPException(status_code=403, detail="Только заведующий может выполнять импорт")

_email_re = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

def _to_bool(v) -> bool | None:
    if v is None or v == "":
        return None
    if isinstance(v, bool):
        return v
    s = str(v).strip().lower()
    if s in ("1", "true", "yes", "y", "да"):
        return True
    if s in ("0", "false", "no", "n", "нет"):
        return False
    return None

@router.post("/rooms", response_model=ImportResult)
async def import_rooms_xlsx(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
):
    _ensure_head(current)

    if not file.filename.lower().endswith(".xlsx"):
        raise HTTPException(400, "Только .xlsx")

    data = await file.read()
    try:
        rows = read_sheet_rows_xlsx(data, sheet_name="Rooms")
    except ExcelError as e:
        raise HTTPException(400, str(e))

    inserted = updated = skipped = 0
    errors: list[ImportRowError] = []

    for row in rows:
        excel_row = int(row.get("__row__", 0))
        number = (row.get("number") or "").strip() if isinstance(row.get("number"), str) else row.get("number")
        if number is None:
            number = ""
        number = str(number).strip()

        if not number:
            errors.append(ImportRowError(row=excel_row, field="number", message="required", raw=row))
            continue

        capacity_raw = row.get("capacity")
        capacity = None
        if capacity_raw not in (None, ""):
            try:
                capacity = int(capacity_raw)
                if capacity < 1 or capacity > 20:
                    raise ValueError()
            except Exception:
                errors.append(ImportRowError(row=excel_row, field="capacity", message="must be int 1..20", raw=row))
                continue

        # upsert by room.number
        res = await db.execute(select(Room).where(Room.number == number))
        room = res.scalar_one_or_none()
        if room is None:
            db.add(Room(number=number, capacity=capacity))
            inserted += 1
        else:
            # update only if changed
            if room.capacity != capacity:
                room.capacity = capacity
                updated += 1
            else:
                skipped += 1

    await db.commit()
    audit_log("rooms_imported", entity_type="room", detail={"inserted": inserted, "updated": updated, "skipped": skipped})
    return ImportResult(total_rows=len(rows), inserted=inserted, updated=updated, skipped=skipped, errors=errors)


@router.post("/students", response_model=ImportResult)
async def import_students_xlsx(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
):
    _ensure_head(current)

    if not file.filename.lower().endswith(".xlsx"):
        raise HTTPException(400, "Только .xlsx")

    data = await file.read()
    try:
        rows = read_sheet_rows_xlsx(data, sheet_name="Students")
    except ExcelError as e:
        raise HTTPException(400, str(e))

    inserted = updated = skipped = 0
    errors: list[ImportRowError] = []

    for row in rows:
        excel_row = int(row.get("__row__", 0))

        email = (row.get("email") or "").strip()
        full_name = row.get("full_name")
        if isinstance(full_name, str):
            full_name = full_name.strip() or None

        phone = row.get("phone")
        if isinstance(phone, str):
            phone = phone.strip() or None

        password = (str(row.get("password")) or "").strip()

        # optional: is_active
        is_active_raw = row.get("is_active")
        is_active = _to_bool(is_active_raw)

        if not email or not _email_re.match(email):
            errors.append(ImportRowError(row=excel_row, field="email", message="invalid email", raw=row))
            continue

        if not password:
            errors.append(ImportRowError(row=excel_row, field="password", message="required", raw=row))
            continue

        password_hash = pwd_context.hash(password)

        res = await db.execute(select(User).where(User.email == email))
        u = res.scalar_one_or_none()

        if u is None:
            u = User(
                email=email,
                password_hash=password_hash,
                role=UserRole.student,
                full_name=full_name,
                phone=phone,
                is_active=True if is_active is None else is_active,
            )
            db.add(u)
            inserted += 1
        else:
            changed = False

            # роль принудительно student
            if u.role != UserRole.student:
                u.role = UserRole.student
                changed = True

            # обновляем поля (если отличаются)
            if u.full_name != full_name:
                u.full_name = full_name
                changed = True

            if u.phone != phone:
                u.phone = phone
                changed = True

            if is_active is not None and u.is_active != is_active:
                u.is_active = is_active
                changed = True

            # пароль обновляем всегда (можно поменять на "если есть колонка update_password")
            if u.password_hash != password_hash:
                u.password_hash = password_hash
                changed = True

            if changed:
                updated += 1
            else:
                skipped += 1

    await db.commit()
    audit_log("students_imported", entity_type="user", detail={"inserted": inserted, "updated": updated, "skipped": skipped})
    return ImportResult(total_rows=len(rows), inserted=inserted, updated=updated, skipped=skipped, errors=errors)
