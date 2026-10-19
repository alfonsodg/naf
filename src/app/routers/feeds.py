"""Feed and entry API. Reader state is owned by Miniflux."""

from typing import Annotated, Any

from fastapi import APIRouter, Body, HTTPException, Path, Query, Request

from app.adapters.http.feed_validator import HttpFeedValidator
from app.adapters.miniflux.client import MinifluxClient
from app.core.config import settings
from app.core.exceptions import MinifluxAPIError
from app.schemas.errors import error_body
from app.schemas.feeds import FeedCreateRequest, FeedUpdateRequest
from app.services.collector import Collector, normalize_entry
from app.services.feed_intake import CandidateFeed, FeedIntake, parse_opml, parse_url_list

router = APIRouter()

LimitQuery = Annotated[int, Query(ge=1, le=500, description="Items per page")]
PageQuery = Annotated[int, Query(ge=1, description="Page number, 1-based")]


def _client() -> MinifluxClient:
    """Build the reader adapter for one request."""
    return MinifluxClient()


def _collector() -> Collector:
    """Build a collector bound to the reader adapter."""
    return Collector(_client())


def _intake() -> FeedIntake:
    """Build the intake service bound to the reader and the HTTP validator."""
    return FeedIntake(_client(), HttpFeedValidator())


def _unavailable(exc: MinifluxAPIError) -> HTTPException:
    """Translate a reader failure into the documented error envelope."""
    return HTTPException(status_code=502, detail=error_body("MINIFLUX_UNAVAILABLE", str(exc)))


def _invalid(code: str, message: str, details: list[dict[str, Any]] | None = None) -> HTTPException:
    """Translate an input problem into the documented error envelope."""
    return HTTPException(status_code=422, detail=error_body(code, message, details))


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


@router.post("/feeds", status_code=201)
async def create_feed(payload: FeedCreateRequest) -> dict[str, Any]:
    """Validate one feed and add it when it answers with real entries."""
    candidate = CandidateFeed(
        url=payload.feed_url,
        categories=(payload.category,) if payload.category else (),
    )
    try:
        result = await _intake().add([candidate])
    except MinifluxAPIError as exc:
        raise _unavailable(exc) from exc

    row = result["feeds"][0]
    if not row["added"]:
        raise _invalid(
            "FEED_REJECTED",
            row["reason"] or "the feed could not be validated",
            [{"url": row["url"], "verdict": row["verdict"], "status_code": row["status_code"]}],
        )
    return {"data": row}


@router.patch("/feeds/{feed_id}")
async def update_feed(
    feed_id: Annotated[int, Path(ge=1)],
    payload: FeedUpdateRequest,
) -> dict[str, Any]:
    """Rename a feed, move it to another category, or pause it."""
    if payload.title is None and payload.category_id is None and payload.disabled is None:
        raise _invalid("FEED_UPDATE_EMPTY", "at least one of title, category_id, or disabled is required")
    try:
        updated = await _client().update_feed(
            feed_id,
            title=payload.title,
            category_id=payload.category_id,
            disabled=payload.disabled,
        )
    except MinifluxAPIError as exc:
        raise _unavailable(exc) from exc
    return {"data": updated}


@router.post("/feeds/{feed_id}/refresh")
async def refresh_feed(feed_id: Annotated[int, Path(ge=1)]) -> dict[str, Any]:
    """Ask the reader to refresh one feed now."""
    try:
        awaited = await _client().refresh_feed(feed_id)
    except MinifluxAPIError as exc:
        raise _unavailable(exc) from exc
    return {"data": {"feed_id": feed_id, "refresh_requested": awaited}}


@router.get("/categories")
async def list_categories() -> list[dict[str, Any]]:
    """List the reader categories."""
    try:
        return await _client().list_categories()
    except MinifluxAPIError as exc:
        raise _unavailable(exc) from exc


@router.post("/feeds/intake", status_code=201)
async def intake_feeds(request: Request) -> dict[str, Any]:
    """Validate and add feeds from a pasted URL list or an OPML document.

    A plain-text body is read as one URL per line. A body carrying XML is read
    as OPML, which preserves the outline nesting as categories. Every input URL
    appears in the report with its verdict, whether it was added or not.
    """
    raw = await request.body()
    if len(raw) > settings.feed_intake_max_bytes:
        raise _invalid(
            "FEED_INTAKE_TOO_LARGE",
            f"payload exceeds {settings.feed_intake_max_bytes} bytes",
        )

    document = raw.decode("utf-8", errors="replace")
    content_type = request.headers.get("content-type", "").lower()

    try:
        if "xml" in content_type or document.lstrip().startswith("<?xml"):
            candidates = parse_opml(document)
        else:
            candidates = parse_url_list(document)
    except ValueError as exc:
        raise _invalid("FEED_INTAKE_INVALID", str(exc)) from exc

    if not candidates:
        raise _invalid("FEED_INTAKE_EMPTY", "no feed URL was found in the payload")

    try:
        return {"data": await _intake().add(candidates)}
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


@router.post("/opml/import", deprecated=True)
async def import_opml(opml: Annotated[str, Body(media_type="text/xml")]) -> dict[str, Any]:
    """Import an OPML document without validating its feeds.

    Deprecated in favour of ``POST /feeds/intake``. Miniflux stores an imported
    OPML without fetching anything, so dead feeds enter the reader silently and
    the call is not atomic. Kept only so existing clients are not broken.
    """
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
