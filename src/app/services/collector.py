"""Ingestion orchestration. Reads reader state; never writes it back."""

from datetime import UTC, datetime
from typing import Any

from app.core.logging import get_logger
from app.core.ports.feed_reader import FeedReader

logger = get_logger(__name__)


class Collector:
    """Collect entries per feed and report per-feed health."""

    def __init__(self, feed_reader: FeedReader) -> None:
        """Bind the collector to a reader implementation."""
        self.feed_reader = feed_reader

    async def collect(self, limit: int = 100, since: datetime | None = None) -> dict[str, Any]:
        """Run one pass; a failing feed must not stop the remaining ones."""
        started = datetime.now(UTC)
        feeds = await self.feed_reader.list_feeds()
        result: dict[str, Any] = {
            "started_at": started.isoformat(),
            "feeds": [],
            "total_entries": 0,
            "errors": [],
        }

        for feed in feeds:
            feed_id = feed["id"]
            try:
                entries = await self.feed_reader.get_entries(feed_id=feed_id, limit=limit)
            except Exception as exc:
                logger.warning(
                    "feed collection failed",
                    extra={"feed_id": feed_id, "error": type(exc).__name__},
                )
                result["errors"].append({"feed_id": feed_id, "error": str(exc)})
                result["feeds"].append(
                    {
                        "feed_id": feed_id,
                        "title": feed.get("title"),
                        "entries": 0,
                        "status": "error",
                        "error": str(exc),
                    }
                )
                continue

            if since is not None:
                entries = [entry for entry in entries if _is_after(entry, since)]

            result["feeds"].append(
                {
                    "feed_id": feed_id,
                    "title": feed.get("title"),
                    "url": feed.get("feed_url"),
                    "entries": len(entries),
                    "status": "ok",
                    "checked_at": feed.get("checked_at"),
                    "parsing_error_count": feed.get("parsing_error_count", 0),
                }
            )
            result["total_entries"] += len(entries)

        result["finished_at"] = datetime.now(UTC).isoformat()
        logger.info(
            "collection finished",
            extra={"count": result["total_entries"], "feeds": len(result["feeds"])},
        )
        return result

    async def health_report(self) -> list[dict[str, Any]]:
        """Summarize freshness and parsing status for every feed."""
        feeds = await self.feed_reader.list_feeds()
        return [normalize_feed(feed) for feed in feeds]


def _is_after(entry: dict[str, Any], since: datetime) -> bool:
    """Keep entries published at or after the cutoff; undated entries stay."""
    published = _parse_timestamp(entry.get("published_at"))
    return published is None or published >= since


def _parse_timestamp(value: str | None) -> datetime | None:
    """Parse an ISO-8601 timestamp, returning None when absent or invalid."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def normalize_feed(feed: dict[str, Any]) -> dict[str, Any]:
    """Map a reader feed to the NAF shape, hiding the reader internals.

    The reader object carries scraper and blocklist rules, the credentials of
    an authenticated feed, and a base64 icon. None of that belongs in the
    complement's API.
    """
    category = feed.get("category") or {}
    return {
        "feed_id": feed.get("id"),
        "title": feed.get("title"),
        "url": feed.get("feed_url"),
        "site_url": feed.get("site_url"),
        "category": category.get("title") if isinstance(category, dict) else None,
        "checked_at": feed.get("checked_at"),
        "parsing_error_count": feed.get("parsing_error_count", 0),
        "parsing_error_message": feed.get("parsing_error_message", ""),
        "disabled": feed.get("disabled", False),
    }


def normalize_entry(entry: dict[str, Any]) -> dict[str, Any]:
    """Map a reader entry to the NAF shape, preserving provenance fields."""
    feed = entry.get("feed") or {}
    return {
        "entry_id": entry.get("id"),
        "guid": entry.get("guid") or entry.get("url"),
        "url": entry.get("url"),
        "title": entry.get("title"),
        "author": entry.get("author"),
        "published_at": entry.get("published_at"),
        "created_at": entry.get("created_at"),
        "status": entry.get("status"),
        "starred": entry.get("starred", False),
        "content": entry.get("content"),
        "reading_time": entry.get("reading_time"),
        "enclosures": entry.get("enclosures") or [],
        "tags": entry.get("tags") or [],
        "feed_id": feed.get("id") or entry.get("feed_id"),
        "feed_title": feed.get("title"),
        "feed_url": feed.get("feed_url"),
        "site_url": feed.get("site_url"),
    }
