"""Ingestion orchestration. Reads reader state; never writes it back."""

from datetime import UTC, datetime
from typing import Any

from app.core.logging import get_logger
from app.core.ports.feed_reader import FeedReader
from app.services.ingestion_runs import RunRecorder

logger = get_logger(__name__)


class Collector:
    """Collect entries per feed and report per-feed health."""

    def __init__(self, feed_reader: FeedReader, runs: RunRecorder | None = None) -> None:
        """Bind the collector to a reader implementation."""
        self.feed_reader = feed_reader
        self.runs = runs

    async def collect(self, limit: int = 100, since: datetime | None = None) -> dict[str, Any]:
        """Run one pass; a failing feed must not stop the remaining ones."""
        started = datetime.now(UTC)
        run_id = self._start_run()
        result: dict[str, Any] = {
            "started_at": started.isoformat(),
            "ingestion_run_id": run_id,
            "feeds": [],
            "total_entries": 0,
            "errors": [],
        }

        # The run is closed on every exit, including the ones that raise: a run
        # left running is indistinguishable from a pass in flight.
        try:
            for feed in await self.feed_reader.list_feeds():
                await self._collect_feed(feed, result, limit, since)
            result["finished_at"] = datetime.now(UTC).isoformat()
        finally:
            self._finish_run(run_id, result)

        logger.info(
            "collection finished",
            extra={
                "count": result["total_entries"],
                "feeds": len(result["feeds"]),
                "ingestion_run_id": run_id,
            },
        )
        return result

    async def _collect_feed(
        self,
        feed: dict[str, Any],
        result: dict[str, Any],
        limit: int,
        since: datetime | None,
    ) -> None:
        """Collect one feed into the pass result, reporting its own failure."""
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
            return

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

    def _start_run(self) -> int | None:
        """Open the ingestion run that records this pass."""
        if self.runs is None:
            return None
        try:
            return self.runs.start("miniflux")
        except Exception as exc:
            # The run is a record of the pass, not the pass itself. A storage
            # problem must never cost the collection.
            logger.warning("could not open the ingestion run", extra={"error": type(exc).__name__})
            return None

    def _finish_run(self, run_id: int | None, result: dict[str, Any]) -> None:
        """Close the ingestion run with the result of the pass."""
        if self.runs is None or run_id is None:
            return
        errors = result.get("errors", [])
        status = "failed" if errors or not result.get("finished_at") else "success"
        try:
            self.runs.finish(run_id, status, int(result.get("total_entries", 0)), errors)
        except Exception as exc:
            logger.warning("could not close the ingestion run", extra={"error": type(exc).__name__})

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
