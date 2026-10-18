"""Health endpoints: liveness plus dependency readiness."""

from typing import Any

from fastapi import APIRouter, Response, status
from sqlalchemy import text

from app.adapters.miniflux.client import MinifluxClient
from app.core.config import settings
from app.core.logging import get_logger
from app.db.session import engine

router = APIRouter()
logger = get_logger(__name__)


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe: the process answers, without touching dependencies."""
    return {"status": "ok", "version": settings.app_version}


@router.get("/health/ready")
async def readiness(response: Response) -> dict[str, Any]:
    """Report whether every dependency the API needs is reachable.

    Returns 503 when any check fails so a load balancer stops routing traffic;
    the body always names each dependency so the failure is diagnosable.
    """
    checks: dict[str, Any] = {}

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        checks["database"] = {"status": "ok"}
    except Exception as exc:
        logger.warning("readiness: database unavailable: %s", type(exc).__name__)
        checks["database"] = {"status": "error", "error": type(exc).__name__}

    try:
        await MinifluxClient().health()
        checks["miniflux"] = {"status": "ok"}
    except Exception as exc:
        logger.warning("readiness: miniflux unavailable: %s", type(exc).__name__)
        checks["miniflux"] = {"status": "error", "error": type(exc).__name__}

    ready = all(check["status"] == "ok" for check in checks.values())
    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {"status": "ok" if ready else "degraded", "checks": checks}
