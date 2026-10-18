"""Health endpoints."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    """Versioned liveness probe."""
    return {"status": "ok"}
