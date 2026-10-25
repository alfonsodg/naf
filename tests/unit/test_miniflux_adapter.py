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


async def test_reader_error_message_is_preserved(client: MinifluxClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """The reader explains refusals in the body; that text is the only diagnostic."""

    async def refused(*args: object, **kwargs: object) -> httpx.Response:
        return _response(
            500,
            json_body={"error_message": "fetcher: access forbidden (403 status code)"},
        )

    monkeypatch.setattr(httpx.AsyncClient, "request", refused)

    with pytest.raises(MinifluxAPIError) as excinfo:
        await client.create_feed("https://blocked.test/feed")

    assert "access forbidden" in str(excinfo.value)
    assert "500" in str(excinfo.value)


async def test_non_json_error_body_is_tolerated(client: MinifluxClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """A plain-text or empty error body must not raise while building the error."""

    async def broken(*args: object, **kwargs: object) -> httpx.Response:
        return _response(502, text="<html>bad gateway</html>")

    monkeypatch.setattr(httpx.AsyncClient, "request", broken)

    with pytest.raises(MinifluxAPIError) as excinfo:
        await client.create_feed("https://a.test/feed")

    assert "502" in str(excinfo.value)


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


async def test_create_feed_posts_to_the_validated_endpoint(
    client: MinifluxClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Feed creation must use POST /v1/feeds, which parses before storing."""
    captured: dict[str, object] = {}

    async def fake_request(method: str, path: str, **kwargs: object) -> httpx.Response:
        captured.update({"method": method, "path": path, **kwargs})
        return _response(201, json_body={"feed_id": 42})

    monkeypatch.setattr(client, "_request", fake_request)
    created = await client.create_feed("https://a.test/feed", category_id=3, disabled=True)

    assert captured["method"] == "POST"
    assert captured["path"] == "/v1/feeds"
    assert captured["json_body"] == {"feed_url": "https://a.test/feed", "disabled": True, "category_id": 3}
    assert created == {"feed_id": 42}


async def test_create_feed_omits_absent_optional_fields(
    client: MinifluxClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An unknown category is omitted so the reader applies its own default."""
    captured: dict[str, object] = {}

    async def fake_request(method: str, path: str, **kwargs: object) -> httpx.Response:
        captured.update(kwargs)
        return _response(201, json_body={"feed_id": 1})

    monkeypatch.setattr(client, "_request", fake_request)
    await client.create_feed("https://a.test/feed")

    assert captured["json_body"] == {"feed_url": "https://a.test/feed", "disabled": False}


async def test_update_feed_sends_only_the_given_fields(client: MinifluxClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """An omitted boolean must never be coerced into False."""
    captured: dict[str, object] = {}

    async def fake_request(method: str, path: str, **kwargs: object) -> httpx.Response:
        captured.update({"method": method, "path": path, **kwargs})
        return _response(201, json_body={"id": 5})

    monkeypatch.setattr(client, "_request", fake_request)
    await client.update_feed(5, disabled=True)

    assert captured["method"] == "PUT"
    assert captured["path"] == "/v1/feeds/5"
    assert captured["json_body"] == {"disabled": True}


async def test_update_feed_without_fields_is_refused(client: MinifluxClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """A patch carrying nothing is refused before the request is made."""

    async def fake_request(*args: object, **kwargs: object) -> httpx.Response:
        raise AssertionError("no request should be made")

    monkeypatch.setattr(client, "_request", fake_request)

    with pytest.raises(MinifluxAPIError):
        await client.update_feed(5)


async def test_categories_are_listed_and_created(client: MinifluxClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """Category listing and creation use the documented endpoints."""
    calls: list[tuple[str, str]] = []

    async def fake_request(method: str, path: str, **kwargs: object) -> httpx.Response:
        calls.append((method, path))
        if method == "GET":
            return _response(200, json_body=[{"id": 1, "title": "Tech"}])
        return _response(201, json_body={"id": 2, "title": "AI"})

    monkeypatch.setattr(client, "_request", fake_request)
    listed = await client.list_categories()
    created = await client.create_category("AI")

    assert calls == [("GET", "/v1/categories"), ("POST", "/v1/categories")]
    assert listed == [{"id": 1, "title": "Tech"}]
    assert created == {"id": 2, "title": "AI"}


async def test_refresh_feed_reports_the_no_content_answer(
    client: MinifluxClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Refresh answers 204, so success is decided by the status code."""

    async def fake_request(method: str, path: str, **kwargs: object) -> httpx.Response:
        assert path == "/v1/feeds/9/refresh"
        return httpx.Response(204, request=httpx.Request("PUT", "http://miniflux.test"))

    monkeypatch.setattr(client, "_request", fake_request)

    assert await client.refresh_feed(9) is True
