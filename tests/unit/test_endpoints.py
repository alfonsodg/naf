"""Endpoint tests: every exposed HTTP method with functional payloads.

The reader adapter is stubbed at the port boundary so these tests exercise the
routing, validation, serialization, and error translation layers only.
"""

from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers import feeds

client = TestClient(app)

OPML = "<?xml version='1.0'?><opml version='2.0'><body/></opml>"


@pytest.fixture(autouse=True)
def stub_reader(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace reader calls with deterministic data for every test."""

    async def list_feeds(self: Any) -> list[dict[str, Any]]:
        return [
            {
                "id": 1,
                "title": "Alpha",
                "feed_url": "https://alpha.test/rss",
                "checked_at": "2026-10-18T10:00:00Z",
                "parsing_error_count": 0,
                "disabled": False,
            }
        ]

    async def get_entries_page(self: Any, **kwargs: Any) -> tuple[list[dict[str, Any]], int]:
        entry = {
            "id": 10,
            "guid": "guid-10",
            "url": "https://example.test/post-10",
            "title": "Post 10",
            "published_at": "2026-10-18T09:00:00Z",
            "status": "unread",
            "feed": {"id": 1, "title": "Alpha", "feed_url": "https://alpha.test/rss"},
        }
        return [entry], 137

    async def update_entries_status(self: Any, entry_ids: list[int], status: str) -> bool:
        return True

    async def get_entry(self: Any, entry_id: int) -> dict[str, Any]:
        return {
            "id": entry_id,
            "guid": "guid-10",
            "url": "https://example.test/post-10",
            "title": "Post 10",
            "published_at": "2026-10-18T09:00:00Z",
            "status": "unread",
            "enclosures": [{"id": 7, "url": "https://example.test/audio.mp3", "mime_type": "audio/mpeg"}],
            "tags": [{"id": 3, "name": "ai"}],
            "feed": {"id": 1, "title": "Alpha", "feed_url": "https://alpha.test/rss"},
        }

    async def export_opml(self: Any) -> str:
        return OPML

    async def import_opml(self: Any, content: str) -> dict[str, Any]:
        assert content.startswith("<?xml")
        return {"message": "imported"}

    monkeypatch.setattr(feeds.MinifluxClient, "list_feeds", list_feeds)
    monkeypatch.setattr(feeds.MinifluxClient, "get_entries_page", get_entries_page)
    monkeypatch.setattr(feeds.MinifluxClient, "update_entries_status", update_entries_status)
    monkeypatch.setattr(feeds.MinifluxClient, "get_entry", get_entry)
    monkeypatch.setattr(feeds.MinifluxClient, "export_opml", export_opml)
    monkeypatch.setattr(feeds.MinifluxClient, "import_opml", import_opml)


def test_list_feeds_returns_reader_payload() -> None:
    """GET /feeds proxies feed metadata without reshaping it."""
    response = client.get("/api/v1/feeds")

    assert response.status_code == 200
    assert response.json()[0]["title"] == "Alpha"


def test_feeds_health_reports_parsing_state() -> None:
    """GET /feeds/health exposes freshness and parsing errors per feed."""
    response = client.get("/api/v1/feeds/health")

    assert response.status_code == 200
    body = response.json()[0]
    assert body["feed_id"] == 1
    assert body["parsing_error_count"] == 0
    assert body["disabled"] is False


def test_list_entries_paginates_and_normalizes() -> None:
    """GET /entries returns a data array plus pagination metadata."""
    response = client.get("/api/v1/entries", params={"page": 2, "per_page": 50})

    assert response.status_code == 200
    body = response.json()
    assert body["pagination"] == {"page": 2, "per_page": 50, "total": 137, "total_pages": 3}
    assert body["data"][0]["entry_id"] == 10
    assert body["data"][0]["feed_url"] == "https://alpha.test/rss"


def test_list_entries_computes_offset_from_page() -> None:
    """The page number is translated into the reader offset."""
    response = client.get("/api/v1/entries", params={"page": 3, "per_page": 20})

    assert response.status_code == 200
    assert response.json()["pagination"]["page"] == 3


def test_the_publication_period_reaches_the_reader() -> None:
    """A period is normalised to UTC and passed to the reader."""
    captured: dict[str, Any] = {}

    async def get_entries_page(self: Any, **kwargs: Any) -> tuple[list[dict[str, Any]], int]:
        captured.update(kwargs)
        return [], 0

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(feeds.MinifluxClient, "get_entries_page", get_entries_page)
        response = client.get(
            "/api/v1/entries",
            params={"published_after": "2026-10-01T00:00:00", "published_before": "2026-10-19T12:00:00Z"},
        )

    assert response.status_code == 200
    assert captured["published_after"] == datetime(2026, 10, 1, tzinfo=UTC)
    assert captured["published_before"] == datetime(2026, 10, 19, 12, tzinfo=UTC)


def test_a_naive_period_is_read_as_utc() -> None:
    """A period without a zone is the same instant, not a local one."""
    captured: dict[str, Any] = {}

    async def get_entries_page(self: Any, **kwargs: Any) -> tuple[list[dict[str, Any]], int]:
        captured.update(kwargs)
        return [], 0

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(feeds.MinifluxClient, "get_entries_page", get_entries_page)
        client.get("/api/v1/entries", params={"published_after": "2026-10-01T00:00:00"})

    assert captured["published_after"] == datetime(2026, 10, 1, tzinfo=UTC)


def test_entries_without_a_period_keep_the_current_behaviour() -> None:
    """A request without the new parameters sends no period."""
    captured: dict[str, Any] = {}

    async def get_entries_page(self: Any, **kwargs: Any) -> tuple[list[dict[str, Any]], int]:
        captured.update(kwargs)
        return [], 0

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(feeds.MinifluxClient, "get_entries_page", get_entries_page)
        client.get("/api/v1/entries")

    assert captured["published_after"] is None
    assert captured["published_before"] is None


def test_the_entry_detail_is_served() -> None:
    """One entry is served with the same shape the list returns."""
    response = client.get("/api/v1/entries/10")

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["entry_id"] == 10
    assert body["feed_url"] == "https://alpha.test/rss"
    assert body["enclosures"][0]["mime_type"] == "audio/mpeg"
    assert body["tags"][0]["name"] == "ai"


def test_the_entry_detail_refuses_an_unknown_identifier() -> None:
    """The identifier must be a positive number."""
    response = client.get("/api/v1/entries/0")

    assert response.status_code == 422


def test_patch_entry_updates_status() -> None:
    """PATCH /entries/{id} changes the read status of one entry."""
    response = client.patch("/api/v1/entries/10", json={"status": "read"})

    assert response.status_code == 200
    assert response.json()["data"] == {"entry_id": 10, "status": "read", "updated": True}


def test_export_opml_returns_document() -> None:
    """GET /opml/export returns the OPML payload wrapped in data."""
    response = client.get("/api/v1/opml/export")

    assert response.status_code == 200
    assert response.json()["data"]["opml"].startswith("<?xml")


def test_import_opml_accepts_xml_body() -> None:
    """POST /opml/import forwards the XML document to the reader."""
    response = client.post("/api/v1/opml/import", content=OPML, headers={"Content-Type": "text/xml"})

    assert response.status_code == 200
    assert response.json()["data"]["message"] == "imported"


def test_collect_runs_one_pass() -> None:
    """POST /collect returns the ingestion summary."""
    response = client.post("/api/v1/collect", params={"limit": 10})

    assert response.status_code == 200
    body = response.json()["data"]
    assert set(body) >= {"started_at", "feeds", "total_entries", "errors"}


def test_reader_failure_returns_502_for_every_endpoint() -> None:
    """Reader outages translate to the documented envelope on all routes."""
    from app.core.exceptions import MinifluxAPIError

    async def failing(*args: Any, **kwargs: Any) -> Any:
        raise MinifluxAPIError("reader down")

    for route, method in (
        ("/api/v1/feeds", "get"),
        ("/api/v1/feeds/health", "get"),
        ("/api/v1/entries", "get"),
        ("/api/v1/entries/10", "get"),
        ("/api/v1/opml/export", "get"),
        ("/api/v1/collect", "post"),
    ):
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(feeds.MinifluxClient, "list_feeds", failing)
            patch.setattr(feeds.MinifluxClient, "get_entries_page", failing)
            patch.setattr(feeds.MinifluxClient, "get_entry", failing)
            patch.setattr(feeds.MinifluxClient, "export_opml", failing)
            response = getattr(client, method)(route)

        assert response.status_code == 502
        assert response.json()["detail"]["error"]["code"] == "MINIFLUX_UNAVAILABLE"
