"""API entry point."""

from fastapi import FastAPI

from app.core.config import settings
from app.routers import feeds, health

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="News aggregator with categorized feeds and on-demand audio reports",
    debug=settings.debug,
)

app.include_router(health.router, prefix=settings.api_prefix, tags=["health"])
app.include_router(feeds.router, prefix=settings.api_prefix, tags=["feeds"])


@app.get("/health", tags=["health"])
async def health_check() -> dict[str, str]:
    """Liveness probe used by deployments."""
    return {"status": "ok", "version": settings.app_version}
