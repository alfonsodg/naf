"""Folder selection: the stored lookup, the merged entry page, and the selector.

SQLite in memory stands in for PostgreSQL and a fake reader for Miniflux, so the
tests exercise the statements, the resolution, the merge, and the HTTP contract
without a service or a network call.
"""

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
from app.routers import entries
from app.services.feed_folders import FeedFolderStore
from app.services.folder_lookup import feed_ids_for_folders

client = TestClient(app)

FEEDS = [
    {
        "id": 1,
        "title": "Alpha",
        "feed_url": "https://alpha.test/rss",
        "category": {"id": 7, "title": "Tech"},
    },
    {
        "id": 2,
        "title": "Beta",
        "feed_url": "https://beta.test/rss",
        "category": {"id": 7, "title": "Tech"},
    },
    {
        "id": 3,
        "title": "Gamma",
        "feed_url": "https://gamma.test/rss",
        "category": {"id": 8, "title": "Science"},
    },
]

STORED = [
    ("https://alpha.test/rss", ["Tech", "AI"]),
    ("https://beta.test/rss", ["AI"]),
    ("https://gamma.test/rss", ["News"]),
]


def _entry(entry_id: int, feed_id: int, feed_url: str, published: str) -> dict[str, Any]:
    """Build one raw reader entry with its feed provenance."""
    return {
        "id": entry_id,
        "guid": f"guid-{entry_id}",
        "url": f"https://example.test/{entry_id}",
        "title": f"Post {entry_id}",
        "published_at": published,
        "status": "unread",
        "feed": {"id": feed_id, "title": f"Feed {feed_id}", "feed_url": feed_url},
    }


class _FolderReader:
    """Reader double that serves the configured feeds and entries by feed id."""

    def __init__(self, feeds: list[dict[str, Any]], by_feed: dict[int, list[dict[str, Any]]]) -> None:
        self.feeds = feeds
        self.by_feed = by_feed
        self.calls: list[dict[str, Any]] = []

    async def list_feeds(self) -> list[dict[str, Any]]:
        """Return the configured feed list."""
        return list(self.feeds)

    async def get_entries_page(self, **kwargs: Any) -> tuple[list[dict[str, Any]], int]:
        """Return one page of the entries stored for the requested feed."""
        self.calls.append(kwargs)
        feed_id = kwargs.get("feed_id")
        limit = int(kwargs.get("limit", 100))
        offset = int(kwargs.get("offset", 0))
        entries_for_feed = self.by_feed.get(feed_id, [])
        return entries_for_feed[offset : offset + limit], len(entries_for_feed)


@pytest.fixture
def session() -> Iterator[Session]:
    """Yield a session bound to a fresh in-memory database, served by the API."""
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    opened = factory()
    app.dependency_overrides[get_session] = lambda: opened
    try:
        store = FeedFolderStore(opened)
        for feed_url, folders in STORED:
            store.record(feed_url, folders)
        yield opened
    finally:
        app.dependency_overrides.clear()
        opened.close()
        engine.dispose()


@pytest.fixture
def reader(monkeypatch: pytest.MonkeyPatch) -> _FolderReader:
    """Replace the reader the entry routes build with the folder double."""
    fake = _FolderReader(
        FEEDS,
        {
            1: [
                _entry(101, 1, "https://alpha.test/rss", "2026-11-01T09:00:00Z"),
                _entry(103, 1, "https://alpha.test/rss", "2026-11-03T09:00:00Z"),
                _entry(105, 1, "https://alpha.test/rss", "2026-11-05T09:00:00Z"),
            ],
            2: [
                _entry(102, 2, "https://beta.test/rss", "2026-11-02T09:00:00Z"),
                _entry(104, 2, "https://beta.test/rss", "2026-11-04T09:00:00Z"),
                _entry(106, 2, "https://beta.test/rss", "2026-11-06T09:00:00Z"),
            ],
            3: [_entry(107, 3, "https://gamma.test/rss", "2026-11-07T09:00:00Z")],
        },
    )
    monkeypatch.setattr(entries, "_client", lambda: fake)
    return fake


def test_the_store_lists_distinct_folders_and_their_feed_urls(session: Session) -> None:
    """The lookup returns sorted names and the URLs stored under one folder."""
    store = FeedFolderStore(session)

    assert store.folders() == ["AI", "News", "Tech"]
    assert store.folder_counts() == [
        {"folder": "AI", "feed_count": 2},
        {"folder": "News", "feed_count": 1},
        {"folder": "Tech", "feed_count": 1},
    ]
    assert store.feed_urls("AI") == ["https://alpha.test/rss", "https://beta.test/rss"]
    assert store.feed_urls("Tech") == ["https://alpha.test/rss"]
    assert store.feed_urls("Missing") == []


async def test_the_folder_resolution_maps_urls_to_reader_identifiers(session: Session, reader: _FolderReader) -> None:
    """A folder becomes the reader ids of its feeds, narrowed by the other filters."""
    assert await _ids(session, reader, ["AI"]) == [1, 2]
    assert await _ids(session, reader, ["Tech", "News"]) == [1, 3]
    assert await _ids(session, reader, ["AI"], feed_id=2) == [2]
    assert await _ids(session, reader, ["AI"], category_id=8) == []
    assert await _ids(session, reader, ["Missing"]) == []


def test_the_entry_list_filters_by_one_folder(session: Session, reader: _FolderReader) -> None:
    """GET /entries with a folder returns only the entries of its feeds."""
    response = client.get("/api/v1/entries", params={"folder": "Tech"})

    assert response.status_code == 200
    body = response.json()
    assert [entry["entry_id"] for entry in body["data"]] == [105, 103, 101]
    assert {entry["feed_url"] for entry in body["data"]} == {"https://alpha.test/rss"}
    assert body["pagination"] == {"page": 1, "per_page": 50, "total": 3, "total_pages": 1}
    assert [call["feed_id"] for call in reader.calls] == [1]


def test_a_feed_in_two_folders_is_read_once(session: Session, reader: _FolderReader) -> None:
    """Requesting both folders of one feed merges its entries without duplicates."""
    response = client.get("/api/v1/entries", params=[("folder", "Tech"), ("folder", "AI")])

    assert response.status_code == 200
    body = response.json()
    identifiers = [entry["entry_id"] for entry in body["data"]]
    assert identifiers == [106, 105, 104, 103, 102, 101]
    assert len(identifiers) == len(set(identifiers))
    assert [call["feed_id"] for call in reader.calls] == [1, 2]


def test_an_unknown_folder_answers_an_empty_page(session: Session, reader: _FolderReader) -> None:
    """A folder with no stored feed selects nothing instead of failing or reading everything."""
    response = client.get("/api/v1/entries", params={"folder": "Missing"})

    assert response.status_code == 200
    body = response.json()
    assert body["data"] == []
    assert body["pagination"] == {"page": 1, "per_page": 50, "total": 0, "total_pages": 0}
    assert reader.calls == []


def test_the_merged_selection_is_paginated_in_naf(session: Session, reader: _FolderReader) -> None:
    """The page is cut after ordering both feeds newest first, not per feed."""
    response = client.get("/api/v1/entries", params={"folder": "AI", "page": 2, "per_page": 2})

    assert response.status_code == 200
    body = response.json()
    assert [entry["entry_id"] for entry in body["data"]] == [104, 103]
    assert body["pagination"] == {"page": 2, "per_page": 2, "total": 6, "total_pages": 3}
    assert {call["limit"] for call in reader.calls} == {4}
    assert {call["offset"] for call in reader.calls} == {0}


def test_a_folder_combines_with_the_other_filters(session: Session, reader: _FolderReader) -> None:
    """A folder narrows the selection instead of replacing the existing filters."""
    response = client.get(
        "/api/v1/entries",
        params={"folder": "AI", "feed_id": 2, "search": "modelo", "tags": ["ai"], "read": False},
    )

    assert response.status_code == 200
    assert [entry["entry_id"] for entry in response.json()["data"]] == [106, 104, 102]
    assert reader.calls[0]["feed_id"] == 2
    assert reader.calls[0]["search"] == "modelo"
    assert reader.calls[0]["tags"] == ["ai"]
    assert reader.calls[0]["read"] is False


def test_the_folders_route_counts_the_feeds_of_each_folder(session: Session) -> None:
    """GET /folders lists the distinct names with their feed count."""
    response = client.get("/api/v1/folders")

    assert response.status_code == 200
    assert response.json()["data"] == [
        {"folder": "AI", "feed_count": 2},
        {"folder": "News", "feed_count": 1},
        {"folder": "Tech", "feed_count": 1},
    ]


async def _ids(
    session: Session,
    reader: _FolderReader,
    folders: list[str],
    *,
    feed_id: int | None = None,
    category_id: int | None = None,
) -> list[int]:
    """Resolve the folders to reader identifiers for the test."""
    return await feed_ids_for_folders(
        reader,
        FeedFolderStore(session),
        folders,
        feed_id=feed_id,
        category_id=category_id,
    )
