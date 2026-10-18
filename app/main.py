from fastapi import FastAPI

from app.core.config import settings
from app.api.routes import health

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="News aggregator with categorized feeds and on-demand audio reports",
    debug=settings.debug,
)

app.include_router(health.router, prefix=settings.api_prefix, tags=["health"])


@app.get("/health")
async def health_check() -> dict:
    return {"status": "ok", "version": settings.app_version}


@app.get("/")
async def root() -> dict:
    return {"message": "NAF API", "version": settings.app_version}
