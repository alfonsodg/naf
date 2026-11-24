"""Pilot metrics: one reading of ingestion, reports, audio, and freshness."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.adapters.miniflux.client import MinifluxClient
from app.core.config import settings as app_settings
from app.core.logging import get_logger
from app.core.ports.feed_reader import FeedReader
from app.db.session import get_session
from app.schemas.errors import error_body
from app.schemas.metrics import MetricsSnapshot
from app.services.metrics import MetricsService

router = APIRouter()
logger = get_logger(__name__)

SessionDep = Annotated[Session, Depends(get_session)]
DaysQuery = Annotated[int, Query(ge=1, le=90, description="Observation window in days")]


def _reader() -> FeedReader:
    """Build the reader adapter for one request."""
    return MinifluxClient()


@router.get("/metrics", responses={503: {"description": "The snapshot could not be built"}})
async def read_metrics(session: SessionDep, days: DaysQuery = 7) -> MetricsSnapshot:
    """Return the pilot snapshot for the window that ends now.

    The reader contributes the source block; a reader outage leaves that block
    marked unavailable and the NAF-owned blocks (ingestion, reports, audio)
    still answer. A storage failure answers ``503`` with the documented
    ``METRICS_UNAVAILABLE`` error envelope.
    """
    try:
        snapshot = await MetricsService(session, _reader(), app_settings).snapshot(days)
    except Exception as exc:
        logger.error("metrics snapshot failed", extra={"error": type(exc).__name__})
        raise HTTPException(
            status_code=503,
            detail=error_body("METRICS_UNAVAILABLE", "the metrics snapshot could not be built"),
        ) from exc
    return snapshot
