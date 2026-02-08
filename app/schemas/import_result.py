from pydantic import BaseModel
from typing import Any

class ImportRowError(BaseModel):
    row: int
    field: str
    message: str
    raw: dict[str, Any] | None = None

class ImportResult(BaseModel):
    total_rows: int
    inserted: int
    updated: int
    skipped: int
    errors: list[ImportRowError]
