"""The pilot metrics endpoint: known rows in, known numbers out.

SQLite in memory stands in for PostgreSQL and a fake reader stands in for
Miniflux, so these tests exercise the queries, the arithmetic, the reader
degradation, and the HTTP contract without a service or a network call.
"""

from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from tests.unit.metrics_support import FakeReader, audio, digest, instant, run, settings

from app.db.base import Base
from app.db.session import get_session
from app.main import app
from app.routers import metrics

client = TestClient(app)


@pytest.fixture
def session() -> Iterator[Session]:
    """Yield a session bound to a fresh in-memory database, served by the API."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    opened = factory()
    app.dependency_overrides[get_session] = lambda: opened
    try:
        yield opened
    finally:
        app.dependency_overrides.clear()
        opened.close()
        engine.dispose()


@pytest.fixture
def now() -> datetime:
    """Return one instant with whole seconds, so the seeded values stay exact."""
    return datetime.now(UTC).replace(microsecond=0)


@pytest.fixture
def wire(monkeypatch: pytest.MonkeyPatch) -> Callable[..., None]:
    """Replace the reader and the settings the route builds."""

    def _wire(reader: FakeReader, **overrides: Any) -> None:
        monkeypatch.setattr(metrics, "_reader", lambda: reader)
        monkeypatch.setattr(metrics, "app_settings", settings(**overrides))

    return _wire


def _read(days: int | None = None) -> Any:
    """Call the metrics route with an optional window."""
    params = {} if days is None else {"days": days}
    return client.get("/api/v1/metrics", params=params)


def test_a_known_dataset_yields_known_counts_and_rates(
    session: Session,
    now: datetime,
    wire: Callable[..., None],
) -> None:
    """The snapshot adds up the seeded passes, editions, assets, and checks."""
    run(session, now - timedelta(days=6), "success", 10)
    run(session, now - timedelta(days=5), "success", 6)
    run(session, now - timedelta(days=4), "failed", 3)
    last = run(session, now - timedelta(days=3), "running", 0)
    run(session, now - timedelta(days=10), "success", 99)

    with_latency = [
        digest(session, now - timedelta(days=4), entry_ids=[1], latency_seconds=10),
        digest(session, now - timedelta(days=3), entry_ids=[1, 2], latency_seconds=20),
        digest(session, now - timedelta(days=2), entry_ids=[1, 2, 3], latency_seconds=30),
        digest(session, now - timedelta(days=1), entry_ids=[1, 2, 3, 4], latency_seconds=40),
    ]
    digest(session, now - timedelta(days=1), status="no_news")
    digest(session, now - timedelta(hours=12), status="failed", entry_ids=[1, 2])
    digest(session, now - timedelta(days=10), entry_ids=[1, 2, 3, 4, 5])

    audio(session, with_latency[0], now - timedelta(days=3), 60.5, 1000)
    audio(session, with_latency[0], now - timedelta(days=2), 120.0, 2000)
    audio(session, with_latency[1], now - timedelta(days=1), 30.25, 3000)
    audio(session, with_latency[2], now - timedelta(days=10), 999.0, 9999)
    session.commit()

    feeds = [
        {"id": 1, "checked_at": (now - timedelta(minutes=5)).isoformat(), "parsing_error_count": 0},
        {"id": 2, "checked_at": (now - timedelta(minutes=30)).isoformat(), "parsing_error_count": 0},
        {"id": 3, "checked_at": (now - timedelta(hours=2)).isoformat(), "parsing_error_count": 0},
        {"id": 4, "checked_at": None, "parsing_error_count": 0},
        {"id": 5, "checked_at": (now - timedelta(minutes=1)).isoformat(), "parsing_error_count": 2},
        {"id": 6, "checked_at": None, "parsing_error_count": 3, "disabled": True},
    ]
    wire(FakeReader(feeds))

    response = _read()

    assert response.status_code == 200
    data = response.json()
    assert data["days"] == 7
    sources = data["sources"]
    assert sources["available"] is True
    assert sources["error"] is None
    assert sources["feeds"] == 6
    assert sources["disabled"] == 1
    assert sources["checked_in_window"] == 4
    assert sources["stale"] == 2
    assert sources["parsing_errors"] == 1
    assert instant(sources["newest_checked_at"]) == now - timedelta(minutes=1)
    assert instant(sources["oldest_checked_at"]) == now - timedelta(hours=2)
    assert data["ingestion"] == {
        "runs": 4,
        "successes": 2,
        "failures": 1,
        "running": 1,
        "success_rate": 0.6667,
        "entries": 19,
        "average_entries": 4.75,
        "last_run_id": last,
        "last_status": "running",
    }
    assert data["reports"] == {
        "editions": 6,
        "ready": 4,
        "no_news": 1,
        "failed": 1,
        "average_included_entries": 2.5,
        "p50_seconds": 20.0,
        "p95_seconds": 40.0,
    }
    assert data["audio"] == {
        "assets": 3,
        "duration_seconds": 210.75,
        "size_bytes": 6000,
        "editions_with_audio": 2,
    }


def test_an_empty_database_returns_zeros_and_nulls(session: Session, wire: Callable[..., None]) -> None:
    """No rows at all still answers the full shape with explicit absent values."""
    wire(FakeReader([]))

    response = _read()

    assert response.status_code == 200
    data = response.json()
    assert data["sources"] == {
        "available": True,
        "error": None,
        "feeds": 0,
        "disabled": 0,
        "checked_in_window": 0,
        "stale": 0,
        "parsing_errors": 0,
        "newest_checked_at": None,
        "oldest_checked_at": None,
    }
    assert data["ingestion"] == {
        "runs": 0,
        "successes": 0,
        "failures": 0,
        "running": 0,
        "success_rate": None,
        "entries": 0,
        "average_entries": None,
        "last_run_id": None,
        "last_status": None,
    }
    assert data["reports"] == {
        "editions": 0,
        "ready": 0,
        "no_news": 0,
        "failed": 0,
        "average_included_entries": None,
        "p50_seconds": None,
        "p95_seconds": None,
    }
    assert data["audio"] == {
        "assets": 0,
        "duration_seconds": 0.0,
        "size_bytes": 0,
        "editions_with_audio": 0,
    }


@pytest.mark.parametrize("days", [0, 91, -1])
def test_the_window_bounds_are_enforced(session: Session, wire: Callable[..., None], days: int) -> None:
    """The window only accepts one to ninety days."""
    wire(FakeReader([]))

    response = _read(days)

    assert response.status_code == 422


def test_a_narrow_window_excludes_older_rows(session: Session, now: datetime, wire: Callable[..., None]) -> None:
    """A one-day reading ignores a pass and an edition from two days ago."""
    run(session, now - timedelta(days=2), "success", 5)
    digest(session, now - timedelta(days=2), entry_ids=[1])
    session.commit()
    wire(FakeReader([]))

    response = _read(days=1)

    assert response.status_code == 200
    data = response.json()
    assert data["days"] == 1
    assert data["ingestion"]["runs"] == 0
    assert data["reports"]["editions"] == 0


def test_a_reader_failure_degrades_only_the_source_block(
    session: Session,
    now: datetime,
    wire: Callable[..., None],
) -> None:
    """NAF-owned blocks still answer when the reader cannot list its feeds."""
    run(session, now - timedelta(hours=1), "success", 7)
    digest(session, now - timedelta(hours=2), entry_ids=[1, 2])
    session.commit()
    wire(FakeReader(error=RuntimeError("the reader is down")))

    response = _read()

    assert response.status_code == 200
    data = response.json()
    assert data["sources"] == {
        "available": False,
        "error": "READER_UNAVAILABLE",
        "feeds": 0,
        "disabled": 0,
        "checked_in_window": 0,
        "stale": 0,
        "parsing_errors": 0,
        "newest_checked_at": None,
        "oldest_checked_at": None,
    }
    assert data["ingestion"]["runs"] == 1
    assert data["ingestion"]["success_rate"] == 1.0
    assert data["reports"]["editions"] == 1


def test_an_internal_failure_uses_the_documented_envelope(
    session: Session,
    wire: Callable[..., None],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A storage or query failure answers 503 with the standard error body."""

    async def explode(self: Any, days: int) -> Any:
        raise RuntimeError("the database is down")

    wire(FakeReader([]))
    monkeypatch.setattr(metrics.MetricsService, "snapshot", explode)

    response = _read()

    assert response.status_code == 503
    error = response.json()["detail"]["error"]
    assert error["code"] == "METRICS_UNAVAILABLE"
    assert error["message"]
    assert error["details"] == []
