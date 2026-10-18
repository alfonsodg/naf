from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Query, Body

from app.adapters.miniflux.client import MinifluxClient
from app.services.collector import Collector
from app.core.exceptions import MinifluxAPIError

router = APIRouter()


def get_collector() -> Collector:
    return Collector(MinifluxClient())


@router.get("/feeds")
async def list_feeds() -> List[Dict[str, Any]]:
    try:
        return await MinifluxClient().list_feeds()
    except MinifluxAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.get("/feeds/health")
async def feeds_health() -> List[Dict[str, Any]]:
    try:
        return await get_collector().health_report()
    except MinifluxAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.get("/entries")
async def list_entries(
    feed_id: Optional[int] = None,
    category_id: Optional[int] = None,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    search: Optional[str] = None,
    read: Optional[bool] = None,
    starred: Optional[bool] = None,
) -> List[Dict[str, Any]]:
    try:
        return await get_collector().get_entries(
            feed_id=feed_id,
            category_id=category_id,
            limit=limit,
            offset=offset,
            search=search,
            read=read,
            starred=starred,
        )
    except MinifluxAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.post("/entries/{entry_id}/read")
async def mark_read(entry_id: int) -> Dict[str, Any]:
    try:
        ok = await MinifluxClient().mark_entry_read(entry_id)
        return {"entry_id": entry_id, "read": ok}
    except MinifluxAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.get("/opml/export")
async def export_opml() -> Dict[str, str]:
    try:
        return {"opml": await MinifluxClient().export_opml()}
    except MinifluxAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.post("/opml/import")
async def import_opml(opml: str = Body(..., media_type="text/xml")) -> Dict[str, Any]:
    try:
        return await MinifluxClient().import_opml(opml)
    except MinifluxAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.post("/collect")
async def collect(
    limit: int = Query(default=100, ge=1, le=500),
) -> Dict[str, Any]:
    try:
        return await get_collector().collect(limit=limit)
    except MinifluxAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
