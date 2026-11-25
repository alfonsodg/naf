"""Manual folder assignment and classification corrections from the interface."""

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_session
from app.main import app
from app.models import EntryClassification, FeedFolder
from app.routers import feeds, ui

client = TestClient(app)


class _Reader:
    """Reader double with two subscriptions and no classification work."""

    def __init__(self) -> None:
        self.feeds = [
            {"id": 1, "title": "Alfa", "feed_url": "https://a.test/rss"},
            {"id": 2, "title": "Beta", "feed_url": "https://b.test/rss"},
        ]

    async def list_feeds(self) -> list[dict[str, Any]]:
        return self.feeds


class _Classifier:
    """Classifier double; corrections never reach it."""

    model = "test"


@pytest.fixture
def session() -> Iterator[Session]:
    """Yield a session bound to a fresh in-memory database."""
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
def wire(monkeypatch: pytest.MonkeyPatch) -> _Reader:
    """Point the API and the pages at the same reader and a classifier double."""
    reader = _Reader()
    monkeypatch.setattr(feeds, "_client", lambda: reader)
    monkeypatch.setattr(ui, "_reader", lambda: reader)
    monkeypatch.setattr(ui, "_classifier", lambda: _Classifier())
    return reader


def test_the_api_replaces_the_folders_of_a_feed(session: Session, wire: _Reader) -> None:
    """A feed's folders are replaced as a set, never appended twice."""
    session.add(FeedFolder(feed_url="https://a.test/rss", folder="Vieja"))
    session.commit()

    response = client.put("/api/v1/feeds/1/folders", json={"folders": ["AI", "Hardware", "AI"]})

    assert response.status_code == 200
    stored = session.query(FeedFolder).filter_by(feed_url="https://a.test/rss").all()
    assert sorted(row.folder for row in stored) == ["AI", "Hardware"]


def test_the_api_refuses_an_unknown_feed(session: Session, wire: _Reader) -> None:
    """An identifier the reader does not have is a 404 with the envelope."""
    response = client.put("/api/v1/feeds/99/folders", json={"folders": ["AI"]})

    assert response.status_code == 404
    assert response.json()["detail"]["error"]["code"] == "FEED_NOT_FOUND"


def test_the_folders_page_shows_and_saves_the_set(session: Session, wire: _Reader) -> None:
    """The form starts from the stored folders and replaces them on submit."""
    session.add(FeedFolder(feed_url="https://a.test/rss", folder="AI"))
    session.commit()

    page = client.get("/sources/1/folders")
    assert page.status_code == 200
    assert 'value="AI"' in page.text

    saved = client.post("/ui/feeds/1/folders", data={"folders": "AI, Hardware"}, follow_redirects=False)
    assert saved.status_code == 303
    assert saved.headers["location"] == "/sources?notice=folders"
    stored = session.query(FeedFolder).filter_by(feed_url="https://a.test/rss").all()
    assert sorted(row.folder for row in stored) == ["AI", "Hardware"]


def test_the_classifications_page_lists_and_corrects(session: Session, wire: _Reader) -> None:
    """A saved suggestion becomes the user's correction from the page."""
    row = EntryClassification(entry_id=7, category="Otra", tags=["x"], source="auto")
    session.add(row)
    session.commit()

    page = client.get("/classifications")
    assert page.status_code == 200
    assert "Automática" in page.text

    saved = client.post(
        "/ui/classifications/7", data={"category": "Ciencia", "tags": "espacio, luna"}, follow_redirects=False
    )
    assert saved.status_code == 303
    session.refresh(row)
    assert row.category == "Ciencia"
    assert row.tags == ["espacio", "luna"]
    assert row.source == "user"


def test_correcting_an_unknown_entry_is_not_found(session: Session, wire: _Reader) -> None:
    """A correction without a stored suggestion is a 404 page."""
    response = client.post("/ui/classifications/99", data={"category": "Ciencia"})

    assert response.status_code == 404
