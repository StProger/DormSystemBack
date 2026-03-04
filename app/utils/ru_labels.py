# app/utils/ru_labels.py
from __future__ import annotations
from enum import Enum
from typing import Any

TICKET_STATUS_RU = {
    "pending": "В обработке",
    "in_work": "В работе",
    "done": "Готово",
    "rejected": "Отклонено",
}

TICKET_TYPE_RU = {
    "repair": "Ремонт",
    "service": "Обслуживание",
    "receipt": "Квитанция",
    "bulky_inout": "Крупногабарит (внос/вынос)",
}

GUEST_STATUS_RU = {
    "pending": "Ожидает",
    "approved": "Одобрено",
    "rejected": "Отклонено",
    "checked_in": "Вошёл",
    "checked_out": "Вышел",
    "expired": "Истёк срок",
}

def normalize_key(v: Any) -> str:
    """Enum -> value; 'TicketStatus.pending' -> 'pending'; иначе str(v)."""
    if v is None:
        return ""
    if isinstance(v, Enum):
        return str(v.value)

    s = str(v).strip().strip("'").strip('"')
    if "." in s:
        s = s.split(".")[-1]
    return s

def ru(map_: dict[str, str], v: Any) -> str:
    key = normalize_key(v)
    return map_.get(key, key)