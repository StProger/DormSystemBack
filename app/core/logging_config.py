"""Structured JSON logging with Logstash integration."""

import logging
import sys
from contextvars import ContextVar
from datetime import datetime, timezone

from pythonjsonlogger import json as jsonlogger

trace_id_ctx: ContextVar[str] = ContextVar("trace_id", default="-")
user_id_ctx: ContextVar[str] = ContextVar("user_id", default="-")


class TraceIdFilter(logging.Filter):
    """Inject trace_id and user_id from contextvars into every LogRecord."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.trace_id = trace_id_ctx.get("-")  # type: ignore[attr-defined]
        record.user_id = user_id_ctx.get("-")  # type: ignore[attr-defined]
        return True


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """JSON formatter with fields expected by Logstash/Kibana."""

    def add_fields(self, log_record: dict, record: logging.LogRecord, message_dict: dict) -> None:
        super().add_fields(log_record, record, message_dict)
        log_record["@timestamp"] = datetime.now(timezone.utc).isoformat()
        log_record["service"] = "dorm-api"
        log_record["level"] = record.levelname
        log_record["logger_name"] = record.name
        log_record["trace_id"] = getattr(record, "trace_id", "-")
        log_record["user_id"] = getattr(record, "user_id", "-")


def setup_logging() -> None:
    """Initialize structured JSON logging with optional Logstash handler."""
    from .config import get_settings
    settings = get_settings()

    root = logging.getLogger()
    root.setLevel(logging.INFO)

    # Remove existing handlers to avoid duplicates on reload
    root.handlers.clear()

    trace_filter = TraceIdFilter()

    # Console handler — structured JSON to stdout
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(CustomJsonFormatter())
    console.addFilter(trace_filter)
    root.addHandler(console)

    # Logstash handler — async TCP
    if settings.LOGSTASH_ENABLED:
        try:
            from logstash_async.handler import AsynchronousLogstashHandler

            logstash_handler = AsynchronousLogstashHandler(
                host=settings.LOGSTASH_HOST,
                port=settings.LOGSTASH_PORT,
                transport="logstash_async.transport.TcpTransport",
                database_path=None,  # no local cache DB
            )
            logstash_handler.setLevel(logging.INFO)
            logstash_handler.addFilter(trace_filter)
            root.addHandler(logstash_handler)
        except Exception as e:
            logging.getLogger(__name__).warning("Failed to init Logstash handler: %s", e)

    # Suppress noisy loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
