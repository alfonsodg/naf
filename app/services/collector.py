from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from app.contracts.feed_reader import FeedReader


class Collector:
    """Syncs feed/entry metadata from the reader (Miniflux) via its public API.

    Ownership rule: this class never writes reader state into NAF and never
    touches Miniflux tables directly. It only reads through FeedReader.
    """

    def __init__(self, feed_reader: FeedReader):
        self.feed_reader = feed_reader

    async def collect(
        self, limit: int = 100, since: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Collect entries grouped per feed and report per-feed health."""
        started = datetime.now(timezone.utc)
        feeds = await self.feed_reader.list_feeds()
        result: Dict[str, Any] = {
            "started_at": started.isoformat(),
            "feeds": [],
            "total_entries": 0,
            "errors": [],
        }

        for feed in feeds:
            feed_id = feed["id"]
            try:
                entries = await self.feed_reader.get_entries(
                    feed_id=feed_id, limit=limit
                )
            except (
                Exception
            ) as exc:  # per-feed isolation: one failure must not stop others
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
                entries = [
                    e
                    for e in entries
                    if self._parse_dt(e.get("published_at")) is None
                    or self._parse_dt(e.get("published_at")) >= since
                ]

            normalized = [self._normalize(e) for e in entries]
            result["feeds"].append(
                {
                    "feed_id": feed_id,
                    "title": feed.get("title"),
                    "url": feed.get("feed_url"),
                    "entries": len(normalized),
                    "status": "ok",
                    "checked_at": feed.get("checked_at"),
                    "parsing_error_count": feed.get("parsing_error_count", 0),
                }
            )
            result["total_entries"] += len(normalized)

        result["finished_at"] = datetime.now(timezone.utc).isoformat()
        return result

    @staticmethod
    def _parse_dt(value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None

    @staticmethod
    def _normalize(entry: Dict[str, Any]) -> Dict[str, Any]:
        """Keep provenance intact; never rewrite source fields."""
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
            "feed_id": feed.get("id") or entry.get("feed_id"),
            "feed_title": feed.get("title"),
            "feed_url": feed.get("feed_url"),
            "site_url": feed.get("site_url"),
        }

    async def get_entries(self, **kwargs) -> List[Dict[str, Any]]:
        entries = await self.feed_reader.get_entries(**kwargs)
        return [self._normalize(e) for e in entries]

    async def health_report(self) -> List[Dict[str, Any]]:
        feeds = await self.feed_reader.list_feeds()
        return [
            {
                "feed_id": f.get("id"),
                "title": f.get("title"),
                "url": f.get("feed_url"),
                "checked_at": f.get("checked_at"),
                "parsing_error_count": f.get("parsing_error_count", 0),
                "parsing_error_message": f.get("parsing_error_message", ""),
                "disabled": f.get("disabled", False),
            }
            for f in feeds
        ]
