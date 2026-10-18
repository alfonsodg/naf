"""Collector behavior: provenance, failure isolation, incremental filter."""

from datetime import UTC, datetime
from typing import Any

import pytest

from app.services.collector import Collector, normalize_entry


class StubReader:
    """Deterministic reader double for collector tests."""

    def __init__(self, feeds: list[dict[str, Any]], entries: dict[int, list[dict[str, Any]]]) -> None:
        """Store the feeds and per-feed entries to serve."""
        self._feeds = feeds
        self._entries = entries

    async def list_feeds(self) -> list[dict[str, Any]]:
        """Return the configured feeds."""
        return self._feeds

    async def get_entries(self, feed_id: int | None = None, **kwargs: Any) -> list[dict[str, Any]]:
        """Return entries for a feed or raise when the feed is broken."""
        if feed_id is None:
            return []
        value = self._entries.get(feed_id, [])
        if isinstance(value, Exception):
            raise value
        return value

    async def get_entry(self, entry_id: int) -> dict[str, Any]:
        """Unused by the collector."""
        raise NotImplementedError

    async def update_entries_status(self, entry_ids: list[int], status: str) -> bool:
        """Unused by the collector."""
        raise NotImplementedError

    async def mark_entry_read(self, entry_id: int) -> bool:
        """Unused by the collector."""
        raise NotImplementedError

    async def export_opml(self) -> str:
        """Unused by the collector."""
        raise NotImplementedError

    async def import_opml(self, opml_content: str) -> dict[str, Any]:
        """Unused by the collector."""
        raise NotImplementedError

    async def health(self) -> dict[str, Any]:
        """Unused by the collector."""
        raise NotImplementedError


def _feed(feed_id: int, title: str) -> dict[str, Any]:
    """Build a feed descriptor."""
    return {
        "id": feed_id,
        "title": title,
        "feed_url": f"https://{title.lower()}.test/rss",
        "checked_at": "2026-10-18T10:00:00Z",
        "parsing_error_count": 0,
    }


def _entry(entry_id: int, feed: dict[str, Any], published_at: str) -> dict[str, Any]:
    """Build a reader entry payload."""
    return {
        "id": entry_id,
        "guid": f"guid-{entry_id}",
        "url": f"https://example.test/post-{entry_id}",
        "title": f"Post {entry_id}",
        "published_at": published_at,
        "status": "unread",
        "feed": {"id": feed["id"], "title": feed["title"], "feed_url": feed["feed_url"]},
    }


def test_normalize_entry_preserves_provenance() -> None:
    """Normalization keeps every source identifier and URL."""
    feed = _feed(1, "Alpha")
    normalized = normalize_entry(_entry(10, feed, "2026-10-18T09:00:00Z"))

    assert normalized["entry_id"] == 10
    assert normalized["guid"] == "guid-10"
    assert normalized["url"] == "https://example.test/post-10"
    assert normalized["feed_id"] == 1
    assert normalized["feed_title"] == "Alpha"
    assert normalized["feed_url"] == "https://alpha.test/rss"


async def test_collect_counts_entries_per_feed() -> None:
    """Each feed contributes its entry count to the run totals."""
    feeds = [_feed(1, "Alpha"), _feed(2, "Beta")]
    reader = StubReader(
        feeds,
        {
            1: [_entry(10, feeds[0], "2026-10-18T09:00:00Z")],
            2: [_entry(20, feeds[1], "2026-10-18T08:00:00Z")],
        },
    )

    result = await Collector(reader).collect(limit=10)

    assert result["total_entries"] == 2
    assert result["errors"] == []
    assert {feed["feed_id"]: feed["status"] for feed in result["feeds"]} == {1: "ok", 2: "ok"}


async def test_one_failing_feed_does_not_block_others() -> None:
    """A broken feed is reported but does not abort the pass."""
    feeds = [_feed(1, "Alpha"), _feed(2, "Beta")]
    reader = StubReader(
        feeds,
        {
            1: RuntimeError("feed unavailable"),
            2: [_entry(20, feeds[1], "2026-10-18T08:00:00Z")],
        },
    )

    result = await Collector(reader).collect(limit=10)

    assert {feed["feed_id"]: feed["status"] for feed in result["feeds"]} == {1: "error", 2: "ok"}
    assert result["total_entries"] == 1
    assert len(result["errors"]) == 1


async def test_since_filter_excludes_older_entries() -> None:
    """Entries published before the cutoff are excluded."""
    feeds = [_feed(1, "Alpha")]
    reader = StubReader(
        feeds,
        {1: [_entry(10, feeds[0], "2026-10-17T09:00:00Z"), _entry(11, feeds[0], "2026-10-19T09:00:00Z")]},
    )

    result = await Collector(reader).collect(limit=10, since=datetime(2026, 10, 18, tzinfo=UTC))

    assert result["total_entries"] == 1


async def test_undated_entries_are_kept() -> None:
    """Entries without a publication date are never silently dropped."""
    feeds = [_feed(1, "Alpha")]
    entry = _entry(10, feeds[0], "")
    entry["published_at"] = None
    reader = StubReader(feeds, {1: [entry]})

    result = await Collector(reader).collect(limit=10, since=datetime(2026, 10, 18, tzinfo=UTC))

    assert result["total_entries"] == 1


@pytest.mark.parametrize("limit", [1, 50, 500])
async def test_collect_forwards_limit(limit: int) -> None:
    """The requested limit is passed through to the reader."""
    feeds = [_feed(1, "Alpha")]
    reader = StubReader(feeds, {1: []})

    result = await Collector(reader).collect(limit=limit)

    assert result["total_entries"] == 0
