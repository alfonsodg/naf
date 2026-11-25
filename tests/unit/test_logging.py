"""Structured logging behavior."""

import json
import logging

from app.core.logging import JsonFormatter, get_logger


def test_json_formatter_emits_valid_json() -> None:
    """Every record renders as one parseable JSON object."""
    record = logging.LogRecord(
        name="app.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="collection finished",
        args=(),
        exc_info=None,
    )
    record.count = 42

    payload = json.loads(JsonFormatter().format(record))

    assert payload["level"] == "INFO"
    assert payload["logger"] == "app.test"
    assert payload["message"] == "collection finished"
    assert payload["count"] == 42


def test_json_formatter_includes_known_correlation_ids() -> None:
    """Correlation identifiers are promoted to top-level fields."""
    record = logging.LogRecord(
        name="app.test",
        level=logging.WARNING,
        pathname=__file__,
        lineno=1,
        msg="feed failed",
        args=(),
        exc_info=None,
    )
    record.feed_id = 7
    record.ingestion_run_id = "run-1"

    payload = json.loads(JsonFormatter().format(record))

    assert payload["feed_id"] == 7
    assert payload["ingestion_run_id"] == "run-1"


def test_get_logger_returns_named_logger() -> None:
    """Loggers are resolved by module name."""
    assert get_logger("app.services.collector").name == "app.services.collector"
