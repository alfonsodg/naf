"""Feed validator transport policy: redirects, address pinning, ordering, and retries."""

import asyncio

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


def _ipv4(*octets: int) -> str:
    """Assemble a dotted-quad address from its octets."""
    return ".".join(str(octet) for octet in octets)


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


class _TrackedChunks(httpx.AsyncByteStream):
    """A body that counts how many chunks the reader actually pulled."""

    def __init__(self, count: int, size: int) -> None:
        self.count = count
        self.size = size
        self.consumed = 0

    async def __aiter__(self) -> object:
        for _ in range(self.count):
            self.consumed += 1
            yield b"x" * self.size


async def test_the_body_is_capped_while_it_is_read() -> None:
    """A body over the limit stops being read, so it never lands in memory."""
    body = _TrackedChunks(count=100, size=1024)
    response = httpx.Response(200, stream=body)

    with pytest.raises(feed_validator.ResponseTooLargeError):
        await feed_validator.read_capped(response, max_bytes=4096)

    assert body.consumed <= 5, "the reader pulled the whole body"


async def test_a_document_over_the_limit_is_reported(
    validator: HttpFeedValidator, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A feed larger than the configured limit is refused with a reason."""
    validator.max_bytes = 64

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<rss><channel>" + "x" * 500 + "</channel></rss>")

    _patch_transport(monkeypatch, handler)
    probe = await validator.validate("https://example.test/feed")

    assert probe.verdict is FeedVerdict.HTTP_ERROR
    assert "limit" in probe.reason


async def test_a_document_under_the_limit_is_still_read(
    validator: HttpFeedValidator, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The cap never changes the verdict for a normal feed."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=RSS_WITH_ITEMS)

    _patch_transport(monkeypatch, handler)
    probe = await validator.validate("https://example.test/feed")

    assert probe.verdict is FeedVerdict.ALIVE
    assert probe.item_count == 2


def test_the_retry_delay_honours_retry_after(validator: HttpFeedValidator) -> None:
    """A host that states a delay is believed."""
    assert validator._retry_delay(httpx.Response(429, headers={"retry-after": "7"}), 0) == 7.0


def test_the_retry_delay_is_clamped(validator: HttpFeedValidator) -> None:
    """A host asking for a day must not hold the request open."""
    assert validator._retry_delay(httpx.Response(429, headers={"retry-after": "86400"}), 0) == 30.0


def test_the_retry_delay_grows_exponentially_without_a_header(validator: HttpFeedValidator) -> None:
    """With no delay stated, each attempt waits twice as long as the last."""
    delays = [validator._retry_delay(httpx.Response(429), attempt) for attempt in range(3)]

    assert delays == [1.0, 2.0, 4.0]
