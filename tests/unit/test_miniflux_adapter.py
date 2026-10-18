"""Contract tests for the Miniflux adapter using recorded shapes."""

import httpx
import pytest

from app.adapters.miniflux.client import MinifluxClient
from app.core.exceptions import MinifluxAPIError
from app.core.ports.feed_reader import FeedReader


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


def test_client_implements_feed_reader_contract(client: MinifluxClient) -> None:
    """The adapter must satisfy the FeedReader port."""
    assert isinstance(client, FeedReader)


async def test_list_feeds_returns_payload(client: MinifluxClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """list_feeds maps the API array without reshaping it."""

    async def fake_request(*args: object, **kwargs: object) -> httpx.Response:
        return _response(200, json_body=[{"id": 1, "title": "Feed A", "feed_url": "https://a.test/rss"}])

    monkeypatch.setattr(client, "_request", fake_request)
    feeds = await client.list_feeds()

    assert feeds == [{"id": 1, "title": "Feed A", "feed_url": "https://a.test/rss"}]


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


async def test_transport_error_becomes_domain_error(client: MinifluxClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """Transport failures must surface as MinifluxAPIError."""

    async def failing_request(*args: object, **kwargs: object) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(httpx.AsyncClient, "request", failing_request)

    with pytest.raises(MinifluxAPIError):
        await client.list_feeds()


async def test_http_error_becomes_domain_error(client: MinifluxClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-2xx responses must surface as MinifluxAPIError."""

    async def unauthorized(*args: object, **kwargs: object) -> httpx.Response:
        return _response(401, json_body={"error_message": "unauthorized"})

    monkeypatch.setattr(httpx.AsyncClient, "request", unauthorized)

    with pytest.raises(MinifluxAPIError):
        await client.list_feeds()


async def test_export_opml_returns_raw_text(client: MinifluxClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """OPML export is XML text, not JSON."""

    async def fake_request(*args: object, **kwargs: object) -> httpx.Response:
        return _response(200, text="<?xml version='1.0'?><opml/>")

    monkeypatch.setattr(client, "_request", fake_request)
    opml = await client.export_opml()

    assert opml.startswith("<?xml")


async def test_health_reads_healthcheck_body(client: MinifluxClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """Health uses the unversioned /healthcheck endpoint."""

    async def fake_request(method: str, path: str, **kwargs: object) -> httpx.Response:
        assert path == "/healthcheck"
        return _response(200, text="OK")

    monkeypatch.setattr(client, "_request", fake_request)
    status = await client.health()

    assert status == {"status": "OK"}


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
