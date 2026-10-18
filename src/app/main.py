"""API entry point."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.routers import feeds, health

logger = get_logger(__name__)


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


@app.get("/health", tags=["health"])
async def health_check() -> dict[str, str]:
    """Deployment liveness probe (unversioned so infra can call it directly)."""
    return {"status": "ok", "version": settings.app_version}
