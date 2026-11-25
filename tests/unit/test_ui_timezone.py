"""The page formatter: stored UTC instants rendered in the configured zone."""

import logging
from datetime import UTC, datetime

import pytest
from tests.ui_fixtures import settings

from app.routers import ui_support

MOMENT = datetime(2026, 11, 24, 15, 30, tzinfo=UTC)


def test_instant_renders_madrid_in_winter() -> None:
    """The winter offset and the CET abbreviation reach the page."""
    assert ui_support.format_instant(MOMENT, "Europe/Madrid") == "24/11/2026 16:30 CET"


def test_instant_renders_madrid_in_summer() -> None:
    """The summer offset switches the abbreviation to CEST."""
    summer = datetime(2026, 7, 1, 12, 0, tzinfo=UTC)

    assert ui_support.format_instant(summer, "Europe/Madrid") == "01/07/2026 14:00 CEST"


def test_instant_renders_lima_without_daylight_saving() -> None:
    """A zone with a fixed offset keeps its numeric abbreviation."""
    assert ui_support.format_instant(MOMENT, "America/Lima") == "24/11/2026 10:30 -05"


def test_instant_reads_a_naive_value_as_utc() -> None:
    """A stored naive instant is UTC, never the server's local time."""
    naive = datetime(2026, 11, 24, 15, 30)

    assert ui_support.format_instant(naive, "UTC") == "24/11/2026 15:30 UTC"


def test_instant_uses_the_configured_timezone(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without an explicit zone the formatter reads the deployment setting."""
    monkeypatch.setattr(ui_support, "app_settings", settings(display_timezone="America/Lima"))

    assert ui_support.format_instant(MOMENT) == "24/11/2026 10:30 -05"


def test_an_unknown_zone_falls_back_to_utc_with_a_warning(caplog: pytest.LogCaptureFixture) -> None:
    """A mistyped IANA zone degrades to UTC instead of failing the page."""
    with caplog.at_level(logging.WARNING, logger="app.routers.ui_support"):
        rendered = ui_support.format_instant(MOMENT, "Mars/Olympus")

    assert rendered == "24/11/2026 15:30 UTC"
    assert "unknown display timezone" in caplog.text


def test_the_timezone_defaults_to_utc() -> None:
    """The deployment setting has a deterministic default."""
    assert settings().display_timezone == "UTC"
