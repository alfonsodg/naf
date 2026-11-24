"""Miniflux adapter entry and delete cases using recorded shapes."""

from datetime import UTC, datetime

import httpx
import pytest

from app.adapters.miniflux.client import MinifluxClient


@pytest.fixture
def client() -> MinifluxClient:
    """Adapter instance bound to test settings."""
    return MinifluxClient()


def _response(status: int, *, json_body: object = None, text: str = "") -> httpx.Response:
    """Build an httpx response with a request attached for raise_for_status."""
    request = httpx.Request("GET", "http://miniflux.test")
    if json_body is not None:
        return httpx.Response(status, json=json_body, request=request)
    return httpx.Response(status, text=text, request=request)


async def test_get_entries_returns_entries_key(client: MinifluxClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """get_entries unwraps the entries collection."""

    async def fake_request(*args: object, **kwargs: object) -> httpx.Response:
        return _response(200, json_body={"entries": [{"id": 10, "title": "Post"}]})

    monkeypatch.setattr(client, "_request", fake_request)
    entries = await client.get_entries(limit=10)

    assert entries == [{"id": 10, "title": "Post"}]


async def test_get_entries_builds_filters(client: MinifluxClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """Filter arguments are translated into API query parameters."""
    captured: dict[str, object] = {}

    async def fake_request(method: str, path: str, **kwargs: object) -> httpx.Response:
        captured.update(kwargs)
        return _response(200, json_body={"entries": []})

    monkeypatch.setattr(client, "_request", fake_request)
    await client.get_entries(feed_id=3, read=True, starred=False, search="model", limit=5, offset=10)

    assert captured["params"] == {
        "limit": 5,
        "offset": 10,
        "feed_id": 3,
        "starred": 0,
        "status": "read",
        "search": "model",
    }


async def test_get_entries_sends_the_publication_period(
    client: MinifluxClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The period is sent as the unix timestamps the reader expects."""
    captured: dict[str, object] = {}

    async def fake_request(method: str, path: str, **kwargs: object) -> httpx.Response:
        captured.update(kwargs)
        return _response(200, json_body={"entries": []})

    monkeypatch.setattr(client, "_request", fake_request)
    await client.get_entries(
        published_after=datetime(2026, 10, 1, tzinfo=UTC),
        published_before=datetime(2026, 10, 19, tzinfo=UTC),
    )

    params = captured["params"]
    assert isinstance(params, dict)
    assert params["published_after"] == int(datetime(2026, 10, 1, tzinfo=UTC).timestamp())
    assert params["published_before"] == int(datetime(2026, 10, 19, tzinfo=UTC).timestamp())


async def test_delete_feed_removes_the_subscription(client: MinifluxClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """The delete call reaches the reader endpoint and reports the outcome."""
    captured: dict[str, object] = {}

    async def fake_request(method: str, path: str, **kwargs: object) -> httpx.Response:
        captured["method"] = method
        captured["path"] = path
        return _response(204)

    monkeypatch.setattr(client, "_request", fake_request)
    removed = await client.delete_feed(42)

    assert removed is True
    assert captured["method"] == "DELETE"
    assert captured["path"] == "/v1/feeds/42"


async def test_get_entries_page_returns_total(client: MinifluxClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """Pagination exposes both the page slice and the unpaginated total."""

    async def fake_request(*args: object, **kwargs: object) -> httpx.Response:
        return _response(200, json_body={"entries": [{"id": 1}], "total": 137})

    monkeypatch.setattr(client, "_request", fake_request)
    entries, total = await client.get_entries_page(limit=50, offset=100)

    assert entries == [{"id": 1}]
    assert total == 137


async def test_get_entries_page_defaults_total_to_zero(client: MinifluxClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """A payload without a total reports zero rather than raising."""

    async def fake_request(*args: object, **kwargs: object) -> httpx.Response:
        return _response(200, json_body={"entries": []})

    monkeypatch.setattr(client, "_request", fake_request)
    entries, total = await client.get_entries_page()

    assert entries == []
    assert total == 0
