"""The NAF-owned stores and the route that reads one of them.

SQLite in memory stands in for PostgreSQL: these tests exercise the statements
and the serialization, which need no service and no environment.
"""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_session
from app.main import app
from app.models import IngestionRun
from app.services.feed_folders import FeedFolderStore
from app.services.ingestion_runs import IngestionRunStore

client = TestClient(app)


@pytest.fixture
def session() -> Iterator[Session]:
    """Yield a session bound to a fresh in-memory database."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    opened = factory()
    try:
        yield opened
    finally:
        opened.close()
        engine.dispose()


def test_a_run_is_opened_and_closed(session: Session) -> None:
    """The run records its state, its count, and a readable error summary."""
    store = IngestionRunStore(session)

    run_id = store.start("miniflux")
    store.finish(run_id, "failed", 7, [{"feed_id": 1, "error": "boom"}])

    row = session.get(IngestionRun, run_id)
    assert row is not None
    assert row.status == "failed"
    assert row.entries_count == 7
    assert row.error_summary == "feed 1: boom"
    assert row.finished_at is not None


def test_a_run_is_open_when_it_starts(session: Session) -> None:
    """A run that was only opened is left in progress, with no finish time."""
    store = IngestionRunStore(session)

    run_id = store.start("miniflux")

    row = session.get(IngestionRun, run_id)
    assert row is not None
    assert row.status == "running"
    assert row.finished_at is None


def test_the_folders_are_replaced_and_not_appended(session: Session) -> None:
    """Recording the same feed twice leaves one row per folder."""
    store = FeedFolderStore(session)

    store.record("https://a.test/feed", ["AI", "Tech"])
    store.record("https://a.test/feed", ["AI"])

    assert store.list_folders() == [{"feed_url": "https://a.test/feed", "folder": "AI"}]


def test_the_folders_route_serves_what_was_stored(session: Session) -> None:
    """GET /feeds/folders reads the table through the request session."""
    FeedFolderStore(session).record("https://a.test/feed", ["AI"])
    app.dependency_overrides[get_session] = lambda: session
    try:
        response = client.get("/api/v1/feeds/folders")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["data"] == [{"feed_url": "https://a.test/feed", "folder": "AI"}]
