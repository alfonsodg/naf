"""Feed validator: every verdict is distinguishable and correctly attributed."""

import asyncio
import socket

import httpx
import pytest

from app.adapters.http import feed_validator
from app.adapters.http.feed_validator import HttpFeedValidator
from app.core.config import settings
from app.core.ports.feed_validator import FeedVerdict

RSS_WITH_ITEMS = """<?xml version="1.0"?>
<rss version="2.0"><channel><title>Example</title>
<item><title>One</title></item><item><title>Two</title></item>
</channel></rss>"""

ATOM_WITH_ENTRIES = """<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
<entry><title>One</title></entry>
</feed>"""

RSS_WITHOUT_ITEMS = """<?xml version="1.0"?>
<rss version="2.0"><channel><title>Empty</title></channel></rss>"""

HTML_PAGE = "<!DOCTYPE html><html><body><h1>Not a feed</h1></body></html>"

PUBLIC_ADDRESS = "93.184.216.34"
PRIVATE_ADDRESS = "10.0.0.5"


async def _resolve(host: str, port: int = 443) -> list[str]:
    """Resolve test hosts to deterministic addresses."""
    if host.startswith("internal"):
        return [PRIVATE_ADDRESS]
    return [PUBLIC_ADDRESS]


@pytest.fixture(autouse=True)
def _resolved_host(monkeypatch: pytest.MonkeyPatch) -> None:
    """Resolve every candidate to a deterministic public address."""
    monkeypatch.setattr(feed_validator, "resolve_host_addresses", _resolve)


@pytest.fixture
def validator() -> HttpFeedValidator:
    """Validator bound to the deterministic test settings."""
    return HttpFeedValidator()


def _transport(handler: object) -> httpx.MockTransport:
    """Wrap a request handler as a mock transport."""
    return httpx.MockTransport(handler)  # type: ignore[arg-type]


def _patch_transport(monkeypatch: pytest.MonkeyPatch, handler: object) -> None:
    """Route every client built by the adapter through a mock transport."""
    original = httpx.AsyncClient

    def factory(*args: object, **kwargs: object) -> httpx.AsyncClient:
        kwargs["transport"] = _transport(handler)
        return original(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(httpx, "AsyncClient", factory)


async def test_live_feed_with_items_is_alive(validator: HttpFeedValidator, monkeypatch: pytest.MonkeyPatch) -> None:
    """A parsed document with entries is the only 'addable' verdict."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=RSS_WITH_ITEMS, headers={"content-type": "application/rss+xml"})

    _patch_transport(monkeypatch, handler)
    probe = await validator.validate("https://example.test/feed")

    assert probe.verdict is FeedVerdict.ALIVE
    assert probe.item_count == 2
    assert probe.status_code == 200


async def test_atom_entries_are_counted(validator: HttpFeedValidator, monkeypatch: pytest.MonkeyPatch) -> None:
    """Atom feeds count <entry>, not only <item>."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=ATOM_WITH_ENTRIES)

    _patch_transport(monkeypatch, handler)
    probe = await validator.validate("https://example.test/atom.xml")

    assert probe.verdict is FeedVerdict.ALIVE
    assert probe.item_count == 1


async def test_empty_feed_is_not_alive(validator: HttpFeedValidator, monkeypatch: pytest.MonkeyPatch) -> None:
    """A 200 response with no entries is the most misleading case and is not 'alive'."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=RSS_WITHOUT_ITEMS)

    _patch_transport(monkeypatch, handler)
    probe = await validator.validate("https://example.test/feed")

    assert probe.verdict is FeedVerdict.EMPTY
    assert probe.status_code == 200
    assert probe.item_count == 0


async def test_html_response_is_an_http_error(validator: HttpFeedValidator, monkeypatch: pytest.MonkeyPatch) -> None:
    """A site page served instead of a feed is not a feed."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=HTML_PAGE, headers={"content-type": "text/html"})

    _patch_transport(monkeypatch, handler)
    probe = await validator.validate("https://example.test/page")

    assert probe.verdict is FeedVerdict.HTTP_ERROR
    assert "not an RSS or Atom" in probe.reason


@pytest.mark.parametrize("status", [401, 403, 405, 406, 409, 418, 429])
async def test_bot_blocking_codes_are_throttled_not_dead(
    validator: HttpFeedValidator, monkeypatch: pytest.MonkeyPatch, status: int
) -> None:
    """A host refusing automated clients is reported as unverified, never as dead."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status)

    _patch_transport(monkeypatch, handler)
    probe = await validator.validate("https://example.test/feed")

    assert probe.verdict is FeedVerdict.THROTTLED
    assert probe.status_code == status


@pytest.mark.parametrize("status", [404, 410, 500, 502, 503])
async def test_dead_feed_codes_are_http_errors(
    validator: HttpFeedValidator, monkeypatch: pytest.MonkeyPatch, status: int
) -> None:
    """Gone and broken feeds are not confused with throttling."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status)

    _patch_transport(monkeypatch, handler)
    probe = await validator.validate("https://example.test/feed")

    assert probe.verdict is FeedVerdict.HTTP_ERROR
    assert probe.status_code == status


async def test_timeout_is_reported_as_timeout(validator: HttpFeedValidator, monkeypatch: pytest.MonkeyPatch) -> None:
    """A host that never answers is a timeout, not an HTTP error."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("too slow", request=request)

    _patch_transport(monkeypatch, handler)
    probe = await validator.validate("https://example.test/feed")

    assert probe.verdict is FeedVerdict.TIMEOUT


async def test_connection_failure_is_an_http_error(
    validator: HttpFeedValidator, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A dead domain resolves to an HTTP error with the exception named."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("name resolution failed", request=request)

    _patch_transport(monkeypatch, handler)
    probe = await validator.validate("https://gone.test/feed")

    assert probe.verdict is FeedVerdict.HTTP_ERROR
    assert "ConnectError" in probe.reason


async def test_internal_target_is_blocked_without_a_request(
    validator: HttpFeedValidator, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A forbidden URL is refused before the transport is ever used."""
    called = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return httpx.Response(200, text=RSS_WITH_ITEMS)

    _patch_transport(monkeypatch, handler)
    probe = await validator.validate("http://localhost:8080/feed")

    assert probe.verdict is FeedVerdict.BLOCKED
    assert called is False


async def test_redirect_into_a_private_address_is_refused(
    validator: HttpFeedValidator, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A public URL must not be able to redirect into the internal network."""
    target = _ipv4(169, 254, 169, 254)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/feed":
            return httpx.Response(302, headers={"location": f"http://{target}/latest/meta-data/"})
        return httpx.Response(200, text=RSS_WITH_ITEMS)

    _patch_transport(monkeypatch, handler)
    probe = await validator.validate("https://example.test/feed")

    assert probe.verdict is FeedVerdict.BLOCKED
    assert "not allowed" in probe.reason


async def test_public_redirect_is_followed(validator: HttpFeedValidator, monkeypatch: pytest.MonkeyPatch) -> None:
    """A legitimate redirect to another public host still resolves."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.headers.get("Host") == "old.test":
            return httpx.Response(301, headers={"location": "https://new.test/feed"})
        return httpx.Response(200, text=RSS_WITH_ITEMS)

    _patch_transport(monkeypatch, handler)
    probe = await validator.validate("https://old.test/feed")

    assert probe.verdict is FeedVerdict.ALIVE


async def test_host_resolving_to_a_private_address_is_blocked(
    validator: HttpFeedValidator, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A public name pointing at the internal network is refused before any request."""
    called = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return httpx.Response(200, text=RSS_WITH_ITEMS)

    _patch_transport(monkeypatch, handler)
    probe = await validator.validate("https://internal.test/feed")

    assert probe.verdict is FeedVerdict.BLOCKED
    assert called is False
    assert PRIVATE_ADDRESS in probe.reason


async def test_redirect_to_a_private_address_is_blocked(
    validator: HttpFeedValidator, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every hop is resolved, so a redirect cannot reach the internal network."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.headers.get("Host") == "example.test":
            return httpx.Response(302, headers={"location": "https://internal.test/latest"})
        return httpx.Response(200, text=RSS_WITH_ITEMS)

    _patch_transport(monkeypatch, handler)
    probe = await validator.validate("https://example.test/feed")

    assert probe.verdict is FeedVerdict.BLOCKED
    assert PRIVATE_ADDRESS in probe.reason


async def test_request_is_pinned_to_the_validated_address(
    validator: HttpFeedValidator, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The socket reaches the validated address while the name is preserved."""
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, text=RSS_WITH_ITEMS)

    _patch_transport(monkeypatch, handler)
    probe = await validator.validate("https://example.test/feed")

    assert probe.verdict is FeedVerdict.ALIVE
    assert seen[0].url.host == PUBLIC_ADDRESS
    assert seen[0].headers["Host"] == "example.test"
    assert seen[0].extensions["sni_hostname"] == "example.test"


async def test_unresolvable_host_is_an_http_error(
    validator: HttpFeedValidator, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A name that does not resolve is an unreachable feed, not a blocked one."""

    async def failing(host: str, port: int = 443) -> list[str]:
        raise socket.gaierror("Name or service not known")

    monkeypatch.setattr(feed_validator, "resolve_host_addresses", failing)
    probe = await validator.validate("https://gone.test/feed")

    assert probe.verdict is FeedVerdict.HTTP_ERROR
    assert "name resolution failed" in probe.reason


async def test_probe_reports_the_effective_url_after_a_redirect(
    validator: HttpFeedValidator, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The reader stores the effective URL, so duplicate checks need it."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.headers.get("Host") == "old.test":
            return httpx.Response(301, headers={"location": "https://new.test/feed"})
        return httpx.Response(200, text=RSS_WITH_ITEMS)

    _patch_transport(monkeypatch, handler)
    probe = await validator.validate("https://old.test/feed")

    assert probe.url == "https://old.test/feed"
    assert probe.final_url == "https://new.test/feed"


async def test_validate_many_preserves_input_order(
    validator: HttpFeedValidator, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Concurrent probing must not reorder the report."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/good":
            return httpx.Response(200, text=RSS_WITH_ITEMS)
        return httpx.Response(404)

    _patch_transport(monkeypatch, handler)
    urls = ["https://example.test/good", "https://example.test/gone", "https://example.test/good2"]
    probes = await validator.validate_many(urls)

    assert [probe.url for probe in probes] == urls
    assert [probe.verdict for probe in probes] == [
        FeedVerdict.ALIVE,
        FeedVerdict.HTTP_ERROR,
        FeedVerdict.HTTP_ERROR,
    ]


async def test_one_host_is_never_probed_beyond_its_limit(
    validator: HttpFeedValidator, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A catalogue pointing many URLs at one server never floods it."""
    active = 0
    peak = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.01)
        active -= 1
        return httpx.Response(200, text=RSS_WITH_ITEMS)

    _patch_transport(monkeypatch, handler)
    urls = [f"https://same.test/feed/{index}" for index in range(8)]

    await validator.validate_many(urls)

    assert peak <= settings.feed_validation_per_host_concurrency


async def test_different_hosts_are_probed_in_parallel(
    validator: HttpFeedValidator, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The per-host limit does not serialize the whole batch."""
    active = 0
    peak = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.01)
        active -= 1
        return httpx.Response(200, text=RSS_WITH_ITEMS)

    _patch_transport(monkeypatch, handler)
    urls = [f"https://host{index}.test/feed" for index in range(4)]

    await validator.validate_many(urls)

    assert peak > 1


async def test_a_rate_limited_host_is_retried(validator: HttpFeedValidator, monkeypatch: pytest.MonkeyPatch) -> None:
    """A host that asks the client to wait is retried after the delay."""
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(429, headers={"retry-after": "0"})
        return httpx.Response(200, text=RSS_WITH_ITEMS)

    _patch_transport(monkeypatch, handler)
    probe = await validator.validate("https://example.test/feed")

    assert attempts == 2
    assert probe.verdict is FeedVerdict.ALIVE


async def test_the_retries_are_bounded(validator: HttpFeedValidator, monkeypatch: pytest.MonkeyPatch) -> None:
    """A host that keeps refusing cannot hold the request open."""
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(429, headers={"retry-after": "0"})

    _patch_transport(monkeypatch, handler)
    probe = await validator.validate("https://example.test/feed")

    assert attempts == settings.feed_validation_max_retries + 1
    assert probe.verdict is FeedVerdict.THROTTLED


async def test_validate_many_without_input_returns_empty(validator: HttpFeedValidator) -> None:
    """An empty candidate list is not an error."""
    assert await validator.validate_many([]) == []


def _ipv4(*octets: int) -> str:
    """Assemble a dotted-quad address from its octets."""
    return ".".join(str(octet) for octet in octets)
