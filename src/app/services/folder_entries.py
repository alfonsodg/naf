"""Serve one page of the entries a folder selection contains.

The reader paginates one feed at a time and knows nothing about the folders the
intake stored. A folder is therefore resolved to its reader feeds, each feed is
read up to the requested page, and the merged selection is deduplicated, ordered
newest first, and cut in NAF. Reading stops at the page boundary instead of
walking the whole folder, so a deep history does not turn one page into an
unbounded number of reader calls.
"""

from datetime import datetime
from typing import Any

from app.core.ports.feed_reader import FeedReader
from app.services.collector import normalize_entry
from app.services.report_selection import deduplicate

READER_PAGE = 100
"""Page size the reader is asked for, kept at its documented maximum."""


async def merged_page(
    reader: FeedReader,
    feed_ids: list[int],
    *,
    limit: int,
    offset: int,
    search: str | None = None,
    read: bool | None = None,
    starred: bool | None = None,
    published_after: datetime | None = None,
    published_before: datetime | None = None,
    tags: list[str] | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """Read the selected feeds up to the requested page and merge their entries.

    An empty selection answers an empty page without calling the reader, which
    is what an unknown folder or a folder whose feeds the reader no longer holds
    produces. The total is the sum each feed reports, so the caller can compute
    the page count of the merged selection.
    """
    if not feed_ids:
        return [], 0

    needed = offset + limit
    merged: list[dict[str, Any]] = []
    total = 0
    for feed_id in feed_ids:
        entries, feed_total = await _read_feed(
            reader,
            feed_id,
            needed,
            search=search,
            read=read,
            starred=starred,
            published_after=published_after,
            published_before=published_before,
            tags=tags,
        )
        merged.extend(normalize_entry(entry) for entry in entries)
        total += feed_total
    return deduplicate(merged)[offset : offset + limit], total


async def _read_feed(
    reader: FeedReader,
    feed_id: int,
    needed: int,
    *,
    search: str | None,
    read: bool | None,
    starred: bool | None,
    published_after: datetime | None,
    published_before: datetime | None,
    tags: list[str] | None,
) -> tuple[list[dict[str, Any]], int]:
    """Read one feed up to ``needed`` entries, in the reader's own page size."""
    collected: list[dict[str, Any]] = []
    total = 0
    while len(collected) < needed:
        size = min(READER_PAGE, needed - len(collected))
        entries, total = await reader.get_entries_page(
            feed_id=feed_id,
            limit=size,
            offset=len(collected),
            search=search,
            read=read,
            starred=starred,
            published_after=published_after,
            published_before=published_before,
            tags=tags,
        )
        collected.extend(entries)
        if len(entries) < size:
            break
    return collected, total
