"""Structured JSON logging for the URL shortener.

Every log line is a single JSON object with:
  timestamp, level, component (logger name), message, request_id (when in Flask context)

Usage:
    from app.logging_config import setup_logging
    setup_logging(app)        # call once in create_app()
"""

import collections
import logging
import os
import threading

from flask import g, has_request_context
from pythonjsonlogger import json as json_logger


# ---------------------------------------------------------------------------
# Custom filter: injects request_id into every log record
# ---------------------------------------------------------------------------

class RequestIdFilter(logging.Filter):
    """Attach ``request_id`` from ``flask.g`` (if available) to every record."""

    def filter(self, record):
        if has_request_context():
            record.request_id = getattr(g, "request_id", "-")
        else:
            record.request_id = "-"
        return True


# ---------------------------------------------------------------------------
# In-memory ring-buffer handler – feeds the /logs viewer
# ---------------------------------------------------------------------------

class MemoryLogHandler(logging.Handler):
    """Store the last *capacity* formatted log records in a thread-safe deque."""

    def __init__(self, capacity: int = 500):
        super().__init__()
        self._buffer: collections.deque[dict] = collections.deque(maxlen=capacity)
        self._lock = threading.Lock()

    def emit(self, record: logging.LogRecord):
        entry = {
            "timestamp": self.format_time(record),
            "level": record.levelname,
            "component": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
        }
        if record.exc_info and record.exc_info[1]:
            entry["exception"] = self.format(record).split("\n")
        with self._lock:
            self._buffer.append(entry)

    @staticmethod
    def format_time(record: logging.LogRecord) -> str:
        from datetime import datetime, timezone

        return datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat()

    def get_entries(self, level: str | None = None, limit: int = 200) -> list[dict]:
        with self._lock:
            entries = list(self._buffer)
        if level:
            entries = [e for e in entries if e["level"] == level.upper()]
        return entries[-limit:]


# Module-level singleton so the /logs route can import it
memory_handler = MemoryLogHandler(capacity=500)


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------


def setup_logging(app):
    """Configure structured JSON logging for the entire application."""

    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()

    # JSON formatter
    formatter = json_logger.JsonFormatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(message)s %(request_id)s",
        rename_fields={
            "asctime": "timestamp",
            "levelname": "level",
            "name": "component",
        },
    )

    # Stream handler -> stdout (Docker / Gunicorn captures this)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    stream_handler.addFilter(RequestIdFilter())

    # Memory handler for /logs viewer
    memory_handler.addFilter(RequestIdFilter())

    # Configure root logger
    root = logging.getLogger()
    root.setLevel(log_level)
    # Remove any existing handlers (Flask/Gunicorn defaults)
    root.handlers.clear()
    root.addHandler(stream_handler)
    root.addHandler(memory_handler)

    # Quiet down noisy libraries
    logging.getLogger("werkzeug").setLevel(logging.WARNING)
    logging.getLogger("peewee").setLevel(logging.WARNING)

    app.logger.info(
        "Structured JSON logging initialised", extra={"log_level": log_level}
    )
