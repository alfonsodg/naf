"""Feed and entry read API. Reader state is owned by Miniflux."""

from typing import Annotated, Any

from fastapi import APIRouter, Body, HTTPException, Path, Query

from app.adapters.miniflux.client import MinifluxClient
from app.core.exceptions import MinifluxAPIError
from app.schemas.errors import error_body
from app.services.collector import Collector, normalize_entry

router = APIRouter()

LimitQuery = Annotated[int, Query(ge=1, le=500, description="Items per page")]
PageQuery = Annotated[int, Query(ge=1, description="Page number, 1-based")]


def _client() -> MinifluxClient:
    """Build the reader adapter for one request."""
    return MinifluxClient()


def _collector() -> Collector:
    """Build a collector bound to the reader adapter."""
    return Collector(_client())


def _unavailable(exc: MinifluxAPIError) -> HTTPException:
    """Translate a reader failure into the documented error envelope."""
    return HTTPException(status_code=502, detail=error_body("MINIFLUX_UNAVAILABLE", str(exc)))


@router.get("/feeds")
async def list_feeds() -> list[dict[str, Any]]:
    """List configured feeds with their health metadata."""
    try:
        return await _client().list_feeds()
    except MinifluxAPIError as exc:
        raise _unavailable(exc) from exc


@router.get("/feeds/health")
async def feeds_health() -> list[dict[str, Any]]:
    """Report per-feed freshness, parsing errors and disabled state."""
    try:
        return await _collector().health_report()
    except MinifluxAPIError as exc:
        raise _unavailable(exc) from exc


@router.get("/entries")
async def list_entries(
    feed_id: int | None = None,
    category_id: int | None = None,
    page: PageQuery = 1,
    per_page: LimitQuery = 50,
    search: str | None = None,
    read: bool | None = None,
    starred: bool | None = None,
) -> dict[str, Any]:
    """List normalized entries preserving provenance, with pagination metadata."""
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


@router.get("/opml/export")
async def export_opml() -> dict[str, Any]:
    """Export subscriptions as OPML for portability."""
    try:
        return {"data": {"opml": await _client().export_opml()}}
    except MinifluxAPIError as exc:
        raise _unavailable(exc) from exc


@router.post("/opml/import")
async def import_opml(opml: Annotated[str, Body(media_type="text/xml")]) -> dict[str, Any]:
    """Import subscriptions from an OPML document."""
    try:
        return {"data": await _client().import_opml(opml)}
    except MinifluxAPIError as exc:
        raise _unavailable(exc) from exc


@router.post("/collect")
async def collect(limit: LimitQuery = 100) -> dict[str, Any]:
    """Run one ingestion pass with per-feed failure isolation."""
    try:
        return {"data": await _collector().collect(limit=limit)}
    except MinifluxAPIError as exc:
        raise _unavailable(exc) from exc
