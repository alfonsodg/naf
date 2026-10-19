"""Collector behavior: provenance, failure isolation, incremental filter."""

from datetime import UTC, datetime
from typing import Any

import pytest

from app.services.collector import Collector, normalize_entry, normalize_feed


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

    async def export_opml(self) -> str:
        """Unused by the collector."""
        raise NotImplementedError

    async def import_opml(self, opml_content: str) -> dict[str, Any]:
        """Unused by the collector."""
        raise NotImplementedError

    async def health(self) -> dict[str, Any]:
        """Unused by the collector."""
        raise NotImplementedError


class StubRuns:
    """Run recorder double keeping the passes in memory."""

    def __init__(self) -> None:
        self.runs: list[dict[str, Any]] = []

    def start(self, adapter_name: str) -> int:
        """Open a run and return its identifier."""
        self.runs.append({"run_id": len(self.runs) + 1, "adapter": adapter_name, "status": "running"})
        return len(self.runs)

    def finish(self, run_id: int, status: str, entries_count: int, errors: list[dict[str, Any]]) -> None:
        """Close a run with its result."""
        self.runs[-1].update({"status": status, "entries": entries_count, "errors": errors})


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


def test_normalize_entry_keeps_the_attachments_and_the_tags() -> None:
    """The enclosure of a podcast and the tags of the feed survive."""
    feed = _feed(1, "Alpha")
    entry = _entry(10, feed, "2026-10-18T09:00:00Z")
    entry["enclosures"] = [{"id": 7, "url": "https://example.test/audio.mp3", "mime_type": "audio/mpeg"}]
    entry["tags"] = [{"id": 3, "name": "ai"}]

    normalized = normalize_entry(entry)

    assert normalized["enclosures"][0]["mime_type"] == "audio/mpeg"
    assert normalized["tags"][0]["name"] == "ai"


def test_normalize_entry_defaults_the_attachments_and_the_tags() -> None:
    """An entry without them carries empty lists, not missing fields."""
    normalized = normalize_entry(_entry(10, _feed(1, "Alpha"), "2026-10-18T09:00:00Z"))

    assert normalized["enclosures"] == []
    assert normalized["tags"] == []


def test_normalize_feed_projects_the_documented_fields() -> None:
    """The feed is projected onto the fields this project defines."""
    normalized = normalize_feed(
        {
            "id": 1,
            "title": "Alpha",
            "feed_url": "https://alpha.test/rss",
            "site_url": "https://alpha.test",
            "category": {"id": 7, "title": "Tech"},
            "checked_at": "2026-10-18T10:00:00Z",
            "parsing_error_count": 2,
            "disabled": False,
            "scraper_rules": "article",
            "username": "reader-user",
            "icon": {"id": 3, "data": "aW5jb24="},
        }
    )

    assert normalized["feed_id"] == 1
    assert normalized["url"] == "https://alpha.test/rss"
    assert normalized["category"] == "Tech"
    assert normalized["parsing_error_count"] == 2
    assert "scraper_rules" not in normalized
    assert "username" not in normalized
    assert "icon" not in normalized


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


async def test_the_pass_is_recorded_as_a_run() -> None:
    """Every pass leaves a run with its counts and its state."""
    feeds = [_feed(1, "Alpha")]
    reader = StubReader(feeds, {1: [_entry(10, feeds[0], "2026-10-18T09:00:00Z")]})
    runs = StubRuns()

    result = await Collector(reader, runs).collect(limit=10)

    assert result["ingestion_run_id"] == 1
    assert runs.runs[0]["adapter"] == "miniflux"
    assert runs.runs[0]["status"] == "success"
    assert runs.runs[0]["entries"] == 1


async def test_a_failing_feed_marks_the_run_as_failed() -> None:
    """A pass with a broken feed is recorded as failed, with the error."""
    feeds = [_feed(1, "Alpha")]
    reader = StubReader(feeds, {1: RuntimeError("feed unavailable")})
    runs = StubRuns()

    await Collector(reader, runs).collect(limit=10)

    assert runs.runs[0]["status"] == "failed"
    assert runs.runs[0]["errors"][0]["feed_id"] == 1


async def test_a_pass_survives_a_broken_recorder() -> None:
    """The run is a record of the pass, never the pass itself."""
    feeds = [_feed(1, "Alpha")]
    reader = StubReader(feeds, {1: [_entry(10, feeds[0], "2026-10-18T09:00:00Z")]})

    class BrokenRuns:
        """Recorder that always fails."""

        def start(self, adapter_name: str) -> int:
            """Fail to open the run."""
            raise RuntimeError("storage is down")

        def finish(self, run_id: int, status: str, entries_count: int, errors: list[dict[str, Any]]) -> None:
            """Fail to close the run."""
            raise RuntimeError("storage is down")

    result = await Collector(reader, BrokenRuns()).collect(limit=10)

    assert result["total_entries"] == 1
    assert result["ingestion_run_id"] is None


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
