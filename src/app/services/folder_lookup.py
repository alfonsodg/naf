"""Resolve the stored folder names to the feeds the reader knows.

A folder is NAF-owned and keyed by feed URL, while the reader selects entries
by feed identifier. The lookup joins both sides: it reads the URLs stored under
the requested folders and keeps the reader feeds published under one of them.
An unknown folder contributes no URL, so it selects nothing instead of failing.
"""

from typing import Any

from app.core.ports.feed_reader import FeedReader
from app.services.feed_folders import FeedFolderStore


async def feed_ids_for_folders(
    reader: FeedReader,
    store: FeedFolderStore,
    folders: list[str],
    *,
    feed_id: int | None = None,
    category_id: int | None = None,
) -> list[int]:
    """Return the reader identifiers of the feeds stored under the folders.

    ``feed_id`` and ``category_id`` narrow the result exactly as the entry list
    applies them, so a folder combines with the existing filters. A feed kept
    under two requested folders appears once, because the URLs are collected in
    a set before the reader is queried.
    """
    urls: set[str] = set()
    for folder in folders:
        urls.update(store.feed_urls(folder))
    if not urls:
        return []

    identifiers: list[int] = []
    for feed in await reader.list_feeds():
        candidate: Any = feed.get("id")
        if not isinstance(candidate, int) or isinstance(candidate, bool):
            continue
        if feed.get("feed_url") not in urls:
            continue
        if feed_id is not None and candidate != feed_id:
            continue
        category: Any = feed.get("category")
        if category_id is not None and (not isinstance(category, dict) or category.get("id") != category_id):
            continue
        if candidate not in identifiers:
            identifiers.append(candidate)
    return identifiers
