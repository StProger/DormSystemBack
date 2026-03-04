from pydantic import BaseModel
from typing import Optional, Any
from datetime import date

class ReportInfo(BaseModel):
    id: str
    title: str
    description: str
    has_date_range: bool

class OccupancySummary(BaseModel):
    rooms_total: int
    capacity_total: int
    occupied_total: int
    free_total: int
    occupancy_rate: float  # 0..1

class OccupancyRoomRow(BaseModel):
    room_id: str
    number: str
    capacity: int
    occupied: int
    free: int
    last_rating: Optional[int] = None
    last_rating_comment: Optional[str] = None
    last_rating_at: Optional[str] = None

class OccupancyReportOut(BaseModel):
    summary: OccupancySummary
    rooms: list[OccupancyRoomRow]

class KVCount(BaseModel):
    key: str
    count: int

class DayCount(BaseModel):
    day: str   # YYYY-MM-DD
    count: int

class TicketsReportOut(BaseModel):
    from_date: Optional[str] = None
    to_date: Optional[str] = None
    by_status: list[KVCount]
    by_type: list[KVCount]
    by_day: list[DayCount]

class GuestPassReportOut(BaseModel):
    from_date: Optional[str] = None
    to_date: Optional[str] = None
    by_status: list[KVCount]
    by_day: list[DayCount]
