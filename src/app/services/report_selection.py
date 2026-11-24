"""Turn a report request into the ordered entries the generator receives.

The reader is queried once per requested feed, once per requested category, or
once for the whole reader. The pages are deduplicated by reader identifier and
ordered newest first; an entry without a publication date is kept and placed
last, because an undated entry is never dropped.
"""

from datetime import UTC, datetime
from typing import Any

from app.core.ports.feed_reader import FeedReader
from app.schemas.reports import ReportCreateRequest


async def select_entries(
    reader: FeedReader,
    request: ReportCreateRequest,
    start: datetime,
    end: datetime,
    limit: int,
) -> list[dict[str, Any]]:
    """Read the requested selection, deduplicate it, and cap it at ``limit``."""
    if request.feed_ids:
        targets: list[tuple[int | None, int | None]] = [(feed_id, None) for feed_id in request.feed_ids]
    elif request.category_ids:
        targets = [(None, category_id) for category_id in request.category_ids]
    else:
        targets = [(None, None)]

    collected: list[dict[str, Any]] = []
    for feed_id, category_id in targets:
        filters: dict[str, Any] = {
            "feed_id": feed_id,
            "category_id": category_id,
            "limit": limit,
            "offset": 0,
            "search": request.search,
            "published_after": start,
            "published_before": end,
            "tags": request.tags,
        }
        if request.read is not None:
            filters["read"] = request.read
        if request.starred is not None:
            filters["starred"] = request.starred
        entries, _total = await reader.get_entries_page(**filters)
        collected.extend(entries)
    return deduplicate(collected)[:limit]


def deduplicate(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop repeated reader identifiers and order the selection newest first."""
    seen: set[Any] = set()
    unique: list[dict[str, Any]] = []
    for entry in entries:
        key = entry.get("entry_id")
        if key is None or key in seen:
            continue
        seen.add(key)
        unique.append(entry)
    unique.sort(key=sort_key, reverse=True)
    return unique


def sort_key(entry: dict[str, Any]) -> tuple[bool, datetime]:
    """Order dated entries first and undated ones last."""
    published = published_at(entry)
    if published is None:
        return False, datetime.min.replace(tzinfo=UTC)
    return True, published


def published_at(entry: dict[str, Any]) -> datetime | None:
    """Read the publication instant of a normalized entry as aware UTC."""
    value = entry.get("published_at")
    if isinstance(value, datetime):
        return utc(value)
    if isinstance(value, str) and value:
        try:
            return utc(datetime.fromisoformat(value.replace("Z", "+00:00")))
        except ValueError:
            return None
    return None


def utc(value: datetime) -> datetime:
    """Return the instant in UTC, reading a naive value as already UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
