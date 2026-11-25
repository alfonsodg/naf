"""Report selection by a stored folder: resolution, forwarding, and persistence.

A fake reader and a fake generator stand in for Miniflux and the model, so the
route is exercised with the real service and a SQLite session.
"""

from collections.abc import Callable, Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import Settings
from app.db.base import Base
from app.db.session import get_session
from app.main import app
from app.models import Digest
from app.routers import reports
from app.schemas.digest import Citation, DigestStory
from app.schemas.digest import Digest as GeneratedDigest
from app.services.feed_folders import FeedFolderStore

client = TestClient(app)

FEEDS = [
    {"id": 4, "title": "Gamma", "feed_url": "https://gamma.test/rss", "category": {"id": 2, "title": "AI"}},
    {"id": 5, "title": "Delta", "feed_url": "https://delta.test/rss", "category": {"id": 2, "title": "AI"}},
]


def _settings() -> Settings:
    """Build settings with the deployment values the route builds."""
    return Settings(
        database_url="postgresql://test:test@localhost:5432/naf_test",
        miniflux_url="http://localhost:8080",
        miniflux_api_key="test-token",
        llm_model="report-model",
    )


def _entry(entry_id: int) -> dict[str, Any]:
    """Build one normalized entry with its provenance."""
    return {
        "entry_id": entry_id,
        "url": f"https://example.test/{entry_id}",
        "title": f"Entrada {entry_id}",
        "published_at": "2026-11-23T09:00:00Z",
        "feed_id": 4,
        "feed_title": "Gamma",
    }


class _FakeReader:
    """Reader double that serves the configured feeds and entries."""

    def __init__(self, entries: list[dict[str, Any]]) -> None:
        self.entries = entries
        self.calls: list[dict[str, Any]] = []

    async def list_feeds(self) -> list[dict[str, Any]]:
        """Return the configured reader feeds."""
        return list(FEEDS)

    async def get_entries_page(self, **kwargs: Any) -> tuple[list[dict[str, Any]], int]:
        """Return the configured entries and record the filters."""
        self.calls.append(kwargs)
        return list(self.entries), len(self.entries)


class _FakeGenerator:
    """Generator double that cites the first selected entry."""

    async def generate(
        self,
        entries: list[dict[str, Any]],
        filters: dict[str, Any],
        since_last: str | None = None,
    ) -> GeneratedDigest:
        """Build one story that cites the first entry."""
        first = entries[0]
        return GeneratedDigest(
            title="Radar semanal",
            summary="Resumen del periodo seleccionado.",
            period_start="2026-11-18T00:00:00+00:00",
            period_end="2026-11-30T00:00:00+00:00",
            stories=[
                DigestStory(
                    title="Historia del periodo",
                    summary="Resumen con atribución.",
                    claims=["La entrada publica una novedad."],
                    citations=[Citation(entry_id=str(first["entry_id"]), entry_url=first["url"], title=first["title"])],
                )
            ],
        )

    def validate_citations(self, digest: GeneratedDigest, entries: list[dict[str, Any]]) -> bool:
        """Accept every generated citation."""
        return True


@pytest.fixture
def session() -> Iterator[Session]:
    """Yield a session bound to a fresh in-memory database, served by the API."""
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
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
def wire(monkeypatch: pytest.MonkeyPatch) -> Callable[[_FakeReader], None]:
    """Replace the reader, the generator, and the settings the route builds."""

    def _wire(reader: _FakeReader) -> None:
        monkeypatch.setattr(reports, "_reader", lambda: reader)
        monkeypatch.setattr(reports, "_generator", lambda: _FakeGenerator())
        monkeypatch.setattr(reports, "app_settings", _settings())

    return _wire


def test_a_report_resolves_the_stored_folders_and_records_them(
    session: Session, wire: Callable[[_FakeReader], None]
) -> None:
    """A folder selection is read through NAF storage and kept for reproducibility."""
    store = FeedFolderStore(session)
    store.record("https://gamma.test/rss", ["AI", "Tech"])
    store.record("https://delta.test/rss", ["AI"])
    reader = _FakeReader([_entry(1)])
    wire(reader)

    response = client.post(
        "/api/v1/reports",
        json={
            "folders": ["AI"],
            "period_start": "2026-11-18T00:00:00Z",
            "period_end": "2026-11-30T00:00:00Z",
        },
    )

    assert response.status_code == 201
    assert [call["feed_id"] for call in reader.calls] == [4, 5]
    stored = session.execute(select(Digest)).scalars().one()
    assert stored.status == "ready"
    assert stored.filters["folders"] == ["AI"]
    assert stored.entry_ids == [1]
