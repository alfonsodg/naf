"""API entry point."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.routers import (
    classification,
    entries,
    feeds,
    health,
    ingestion_runs,
    maintenance,
    metrics,
    relations,
    reports,
    ui,
)

logger = get_logger(__name__)
STATIC_DIR = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Configure logging on startup and record the effective configuration."""
    configure_logging()
    logger.info("starting %s %s", settings.app_name, settings.app_version)
    yield
    logger.info("stopping %s", settings.app_name)


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="News aggregator with categorized feeds and on-demand audio reports",
    debug=settings.debug,
    lifespan=lifespan,
)

app.include_router(health.router, prefix=settings.api_prefix, tags=["health"])
app.include_router(feeds.router, prefix=settings.api_prefix, tags=["feeds"])
app.include_router(entries.router, prefix=settings.api_prefix, tags=["entries"])
app.include_router(classification.router, prefix=settings.api_prefix, tags=["classification"])
app.include_router(ingestion_runs.router, prefix=settings.api_prefix, tags=["ingestion"])
app.include_router(metrics.router, prefix=settings.api_prefix, tags=["metrics"])
app.include_router(maintenance.router, prefix=settings.api_prefix, tags=["maintenance"])
app.include_router(relations.router, prefix=settings.api_prefix, tags=["relations"])
app.include_router(reports.router, prefix=settings.api_prefix, tags=["reports"])
app.include_router(ui.router, tags=["ui"])
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/health", tags=["health"])
async def health_check() -> dict[str, str]:
    """Deployment liveness probe (unversioned so infra can call it directly)."""
    return {"status": "ok", "version": settings.app_version}
