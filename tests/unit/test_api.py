"""API boundary tests: routing, validation, and error envelope."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_root_health_endpoint() -> None:
    """Deployment liveness endpoint responds with ok."""
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_versioned_health_endpoint() -> None:
    """Versioned health endpoint under the API prefix."""
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_unknown_route_returns_404() -> None:
    """No catch-all root route is exposed."""
    assert client.get("/").status_code == 404


def test_entries_rejects_non_positive_page() -> None:
    """Page numbering is validated at the boundary before any reader call."""
    response = client.get("/api/v1/entries", params={"page": 0})

    assert response.status_code == 422


def test_entries_rejects_oversized_page_size() -> None:
    """Per-page size is capped to protect the reader API."""
    response = client.get("/api/v1/entries", params={"per_page": 501})

    assert response.status_code == 422


def test_entry_patch_rejects_invalid_status() -> None:
    """Only read and unread are accepted statuses."""
    response = client.patch("/api/v1/entries/1", json={"status": "archived"})

    assert response.status_code == 422


def test_remove_entry_read_route_is_gone() -> None:
    """The non-standard read endpoint is no longer exposed."""
    assert client.put("/api/v1/entries/1/read").status_code == 404


def test_reader_outage_returns_documented_error_envelope(monkeypatch) -> None:
    """A reader failure surfaces as 502 with the standard error body."""
    from app.core.exceptions import MinifluxAPIError
    from app.routers import feeds

    async def failing_list_feeds(self) -> list[dict[str, object]]:
        raise MinifluxAPIError("reader down")

    monkeypatch.setattr(feeds.MinifluxClient, "list_feeds", failing_list_feeds)
    response = client.get("/api/v1/feeds")

    assert response.status_code == 502
    body = response.json()["detail"]
    assert body["error"]["code"] == "MINIFLUX_UNAVAILABLE"
    assert body["error"]["details"] == []
