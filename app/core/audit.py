"""Audit logging utility for business events."""

import logging
from typing import Any


def audit_log(
    event: str,
    *,
    entity_type: str | None = None,
    entity_id: str | None = None,
    detail: dict[str, Any] | None = None,
    level: int = logging.INFO,
) -> None:
    """Log an audit event. trace_id and user_id are injected by TraceIdFilter."""
    logger = logging.getLogger(f"dorm.audit.{event}")
    extra: dict[str, Any] = {"event": event}
    if entity_type:
        extra["entity_type"] = entity_type
    if entity_id:
        extra["entity_id"] = entity_id
    if detail:
        extra["detail"] = detail
    logger.log(level, event, extra=extra)
