"""Entry API: list, read, and update entries. Reader state is owned by Miniflux."""

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Body, Path, Query

from app.core.exceptions import MinifluxAPIError
from app.routers.feeds import LimitQuery, PageQuery, _client, _unavailable, _utc
from app.services.collector import normalize_entry

router = APIRouter()

TagsQuery = Annotated[
    list[str] | None,
    Query(description="Tag to match; repeat the parameter for several tags, and the reader requires all of them"),
]


@router.get("/entries")
async def list_entries(
    feed_id: int | None = None,
    category_id: int | None = None,
    page: PageQuery = 1,
    per_page: LimitQuery = 50,
    search: str | None = None,
    read: bool | None = None,
    starred: bool | None = None,
    published_after: datetime | None = None,
    published_before: datetime | None = None,
    tags: TagsQuery = None,
) -> dict[str, Any]:
    """List normalized entries preserving provenance, with pagination metadata.

    ``tags`` is forwarded as a repeated parameter and the reader requires an
    entry to carry every requested tag. A request without tags sends none.
    """
    offset = (page - 1) * per_page
    try:
        entries, total = await _client().get_entries_page(
            feed_id=feed_id,
            category_id=category_id,
            limit=per_page,
            offset=offset,
            search=search,
            read=read,
            starred=starred,
            published_after=_utc(published_after),
            published_before=_utc(published_before),
            tags=tags,
        )
    except MinifluxAPIError as exc:
        raise _unavailable(exc) from exc

    total_pages = (total + per_page - 1) // per_page if total else 0
    return {
        "data": [normalize_entry(entry) for entry in entries],
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
        },
    }


@router.get("/entries/{entry_id}")
async def read_entry(entry_id: Annotated[int, Path(ge=1)]) -> dict[str, Any]:
    """Return one entry with the same shape the list returns."""
    try:
        entry = await _client().get_entry(entry_id)
    except MinifluxAPIError as exc:
        raise _unavailable(exc) from exc
    return {"data": normalize_entry(entry)}


@router.patch("/entries/{entry_id}")
async def update_entry(
    entry_id: Annotated[int, Path(ge=1)],
    status: Annotated[str, Body(embed=True, pattern="^(read|unread)$")],
) -> dict[str, Any]:
    """Update the read status of one entry."""
    try:
        updated = await _client().update_entries_status([entry_id], status)
    except MinifluxAPIError as exc:
        raise _unavailable(exc) from exc
    return {"data": {"entry_id": entry_id, "status": status, "updated": updated}}
