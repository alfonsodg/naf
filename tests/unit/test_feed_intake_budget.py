"""The intake budget is a wall-clock bound, not a per-request timeout.

The real validator is used here, because the overrun this guards against comes
from its per-host limit: a chunk of same-host URLs serialises into several
rounds, and a per-request timeout cannot see that.
"""

import asyncio
import time
from typing import Any

import httpx
import pytest

from app.adapters.http import feed_validator
from app.adapters.http.feed_validator import HttpFeedValidator
from app.core.config import settings
from app.core.exceptions import MinifluxAPIError
from app.services.feed_documents import CandidateFeed
from app.services.feed_intake import FeedIntake

PUBLIC_ADDRESS = "93.184.216.34"
SLOW = 0.2
RSS = "<rss version='2.0'><channel><item><title>x</title></item></channel></rss>"


class StubReader:
    """Reader double that records the feeds it is asked to create."""

    def __init__(self) -> None:
        self.created: list[str] = []

    async def list_feeds(self) -> list[dict[str, Any]]:
        return []

    async def list_categories(self) -> list[dict[str, Any]]:
        return []

    async def create_category(self, title: str) -> dict[str, Any]:
        return {"id": 1, "title": title}

    async def create_feed(self, feed_url: str, *, category_id: int | None = None, **kwargs: Any) -> dict[str, Any]:
        self.created.append(feed_url)
        return {"id": 1}

    async def import_opml(self, opml_content: str) -> dict[str, Any]:
        raise MinifluxAPIError("not used here")


async def _resolve(host: str, port: int = 443) -> list[str]:
    """Resolve every test host to one public address."""
    return [PUBLIC_ADDRESS]


async def test_the_call_returns_within_the_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    """Eight same-host candidates cannot outlast the configured budget."""
    monkeypatch.setattr(settings, "feed_intake_time_budget", 0.5)
    monkeypatch.setattr(settings, "feed_validation_timeout", 0.2)
    monkeypatch.setattr(settings, "feed_validation_per_host_concurrency", 2)
    monkeypatch.setattr(settings, "feed_validation_max_retries", 2)
    monkeypatch.setattr(feed_validator, "resolve_host_addresses", _resolve)

    async def handler(request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(SLOW)
        return httpx.Response(200, text=RSS)

    original = httpx.AsyncClient

    def factory(*args: object, **kwargs: object) -> httpx.AsyncClient:
        kwargs["transport"] = httpx.MockTransport(handler)
        return original(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(httpx, "AsyncClient", factory)

    service = FeedIntake(StubReader(), HttpFeedValidator(), None)  # type: ignore[arg-type]
    candidates = [CandidateFeed(url=f"https://same.test/feed/{index}") for index in range(8)]

    started = time.monotonic()
    result = await service.add(candidates)
    elapsed = time.monotonic() - started

    budget = settings.feed_intake_time_budget
    assert elapsed <= budget + settings.feed_validation_timeout, f"took {elapsed:.2f}s against a {budget}s budget"
    assert len(result["feeds"]) == 8, "a candidate was dropped from the report"
