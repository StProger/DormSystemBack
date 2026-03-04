from __future__ import annotations
from datetime import date
import io

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User, UserRole

from app.schemas.reports import (
    ReportInfo,
    OccupancyReportOut, OccupancySummary, OccupancyRoomRow,
    TicketsReportOut, GuestPassReportOut,
)
from app.services.reports_service import occupancy_report, tickets_report, guest_pass_report
from app.core.excel_reports import wb_to_bytes, occupancy_to_wb, tickets_to_wb, guest_pass_to_wb


router = APIRouter(prefix="/reports", tags=["reports"])

def _ensure_reports_access(u: User):
    if u.role not in (UserRole.head, UserRole.comendant, UserRole.guard):
        raise HTTPException(403, "Недостаточно прав")

def _ensure_admin(u: User):
    if u.role not in (UserRole.head, UserRole.comendant):
        raise HTTPException(403, "Недостаточно прав")


@router.get("", response_model=list[ReportInfo])
async def list_reports(current: User = Depends(get_current_user)):
    _ensure_reports_access(current)
    return [
        ReportInfo(id="occupancy", title="Загрузка общежития", description="Вместимость, заселение, свободные места, оценки комнат", has_date_range=False),
        ReportInfo(id="tickets", title="Заявки", description="Статусы/типы заявок и динамика по дням", has_date_range=True),
        ReportInfo(id="guest_passes", title="Гости", description="Статусы гостевых заявок и динамика по дням", has_date_range=True),
    ]


@router.get("/occupancy", response_model=OccupancyReportOut)
async def get_occupancy(
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
):
    _ensure_admin(current)
    summary, rooms = await occupancy_report(db)
    return OccupancyReportOut(
        summary=OccupancySummary(**summary),
        rooms=[OccupancyRoomRow(**r) for r in rooms],
    )


@router.get("/tickets", response_model=TicketsReportOut)
async def get_tickets(
    from_date: date | None = None,
    to_date: date | None = None,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
):
    _ensure_admin(current)
    by_status, by_type, by_day = await tickets_report(db, from_date, to_date)
    return TicketsReportOut(
        from_date=from_date.isoformat() if from_date else None,
        to_date=to_date.isoformat() if to_date else None,
        by_status=by_status,
        by_type=by_type,
        by_day=by_day,
    )


@router.get("/guest-passes", response_model=GuestPassReportOut)
async def get_guest_passes(
    from_date: date | None = None,
    to_date: date | None = None,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
):
    # охраннику можно показать этот отчёт
    if current.role not in (UserRole.head, UserRole.comendant, UserRole.guard):
        raise HTTPException(403)

    by_status, by_day = await guest_pass_report(db, from_date, to_date)
    return GuestPassReportOut(
        from_date=from_date.isoformat() if from_date else None,
        to_date=to_date.isoformat() if to_date else None,
        by_status=by_status,
        by_day=by_day,
    )


@router.get("/{report_id}/export")
async def export_report_xlsx(
    report_id: str,
    from_date: date | None = None,
    to_date: date | None = None,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
):
    _ensure_reports_access(current)

    filename = f"report_{report_id}.xlsx"

    if report_id == "occupancy":
        _ensure_admin(current)
        summary, rooms = await occupancy_report(db)
        wb = occupancy_to_wb(summary, rooms)

    elif report_id == "tickets":
        _ensure_admin(current)
        by_status, by_type, by_day = await tickets_report(db, from_date, to_date)
        wb = tickets_to_wb(
            {"from_date": from_date.isoformat() if from_date else None, "to_date": to_date.isoformat() if to_date else None},
            by_status, by_type, by_day
        )

    elif report_id == "guest_passes":
        # guard allowed
        by_status, by_day = await guest_pass_report(db, from_date, to_date)
        wb = guest_pass_to_wb(
            {"from_date": from_date.isoformat() if from_date else None, "to_date": to_date.isoformat() if to_date else None},
            by_status, by_day
        )
    else:
        raise HTTPException(404, "Неизвестный отчёт")

    data = wb_to_bytes(wb)
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
