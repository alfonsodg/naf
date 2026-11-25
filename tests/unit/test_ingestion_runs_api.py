"""The ingestion run read path: the recorded history served through the API.

SQLite in memory stands in for PostgreSQL: these tests exercise the store
queries, the projection, and the HTTP contract without any service. The write
path is covered by ``test_stores.py`` and ``test_collector.py`` and stays
untouched here.
"""

from collections.abc import Iterator
from datetime import datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_session
from app.main import app
from app.services.ingestion_runs import IngestionRunStore

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


def _finished_run(session: Session, status: str, entries: int, errors: list[dict[str, Any]]) -> int:
    """Record a closed run and return its identifier."""
    store = IngestionRunStore(session)
    run_id = store.start("miniflux")
    store.finish(run_id, status, entries, errors)
    return run_id


def test_the_history_starts_empty(session: Session) -> None:
    """GET /ingestion-runs answers an empty page before any pass is recorded."""
    response = client.get("/api/v1/ingestion-runs")

    assert response.status_code == 200
    assert response.json() == {
        "data": [],
        "pagination": {"page": 1, "per_page": 50, "total": 0, "total_pages": 0},
    }


def test_a_successful_run_is_served(session: Session) -> None:
    """One finished pass carries its state, its count, and its UTC start."""
    run_id = _finished_run(session, "success", 12, [])

    response = client.get(f"/api/v1/ingestion-runs/{run_id}")

    assert response.status_code == 200
    run = response.json()["data"]
    assert run["run_id"] == run_id
    assert run["status"] == "success"
    assert run["entries_count"] == 12
    assert run["errors"] == []
    assert run["error_summary"] == ""
    assert run["finished_at"] is not None
    assert datetime.fromisoformat(run["started_at"].replace("Z", "+00:00")).tzinfo is not None


def test_a_failed_run_keeps_its_per_feed_errors(session: Session) -> None:
    """The failure names the feed, its error, and a readable summary."""
    run_id = _finished_run(session, "failed", 7, [{"feed_id": 4, "error": "timeout"}])

    response = client.get(f"/api/v1/ingestion-runs/{run_id}")

    assert response.status_code == 200
    run = response.json()["data"]
    assert run["status"] == "failed"
    assert run["entries_count"] == 7
    assert run["errors"] == [{"feed_id": 4, "error": "timeout"}]
    assert run["error_summary"] == "feed 4: timeout"


def test_a_running_run_is_distinguishable_from_a_finished_one(session: Session) -> None:
    """An open pass reports its state and has no finish time, even when read."""
    run_id = IngestionRunStore(session).start("miniflux")

    response = client.get(f"/api/v1/ingestion-runs/{run_id}")

    assert response.status_code == 200
    run = response.json()["data"]
    assert run["status"] == "running"
    assert run["finished_at"] is None
    assert run["errors"] == []


def test_an_unknown_identifier_uses_the_documented_envelope(session: Session) -> None:
    """A missing run answers 404 with the standard error envelope."""
    response = client.get("/api/v1/ingestion-runs/999")

    assert response.status_code == 404
    error = response.json()["detail"]["error"]
    assert error["code"] == "INGESTION_RUN_NOT_FOUND"
    assert error["message"]
    assert error["details"] == []


def test_an_invalid_identifier_is_rejected(session: Session) -> None:
    """The identifier must be a positive number."""
    response = client.get("/api/v1/ingestion-runs/0")

    assert response.status_code == 422


def test_the_history_is_ordered_newest_first(session: Session) -> None:
    """The page lists the most recent pass before the older ones."""
    first = _finished_run(session, "success", 1, [])
    second = _finished_run(session, "success", 2, [])

    response = client.get("/api/v1/ingestion-runs")

    assert response.status_code == 200
    assert [run["run_id"] for run in response.json()["data"]] == [second, first]


def test_the_history_paginates(session: Session) -> None:
    """Page two of three runs carries one row and the documented metadata."""
    for _ in range(3):
        _finished_run(session, "success", 0, [])

    response = client.get("/api/v1/ingestion-runs", params={"page": 2, "per_page": 2})

    assert response.status_code == 200
    body = response.json()
    assert body["pagination"] == {"page": 2, "per_page": 2, "total": 3, "total_pages": 2}
    assert len(body["data"]) == 1


def test_the_status_filter_selects_one_state(session: Session) -> None:
    """Only the runs in the requested state are listed and counted."""
    _finished_run(session, "success", 1, [])
    failed = _finished_run(session, "failed", 1, [{"feed_id": 9, "error": "boom"}])

    response = client.get("/api/v1/ingestion-runs", params={"status": "failed"})

    assert response.status_code == 200
    body = response.json()
    assert body["pagination"]["total"] == 1
    assert [run["run_id"] for run in body["data"]] == [failed]


def test_an_unknown_status_is_rejected(session: Session) -> None:
    """The filter only accepts the states a pass can be in."""
    response = client.get("/api/v1/ingestion-runs", params={"status": "archived"})

    assert response.status_code == 422


@pytest.mark.parametrize("params", [{"page": 0}, {"per_page": 0}, {"per_page": 501}])
def test_the_pagination_bounds_are_enforced(session: Session, params: dict[str, int]) -> None:
    """The shared page and limit validators apply to the new route."""
    response = client.get("/api/v1/ingestion-runs", params=params)

    assert response.status_code == 422
