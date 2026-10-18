"""Structured logging configuration.

JSON logs in deployed environments so a collector can parse them; readable
console output in development. Secrets are never logged: callers pass only
identifiers and counts.
"""

import logging
import sys
from typing import Any

from app.core.config import settings


class JsonFormatter(logging.Formatter):
    """Render one log record as a single JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        """Serialize the record with its structured extras."""
        import json

        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key in ("source_id", "ingestion_run_id", "digest_id", "feed_id", "entry_id", "count"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging() -> None:
    """Install the root handler once, with a level taken from settings."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        JsonFormatter() if settings.log_json else logging.Formatter("%(levelname)s %(name)s: %(message)s")
    )

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(settings.log_level.upper())


def get_logger(name: str) -> logging.Logger:
    """Return a logger for a module, relying on configured root handlers."""
    return logging.getLogger(name)
