"""Edition cleanup routes. The cleanup is manual and dry by default."""

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.adapters.storage.local import LocalAudioStorage
from app.core.config import settings as app_settings
from app.db.session import get_session
from app.schemas.errors import error_body
from app.services.maintenance import MaintenanceService

router = APIRouter()
SessionDep = Annotated[Session, Depends(get_session)]

DaysQuery = Annotated[int, Query(ge=1, le=3650, description="Retention window in days")]


def _service(session: Session) -> MaintenanceService:
    """Build the cleanup service with the local audio backend."""
    return MaintenanceService(session, LocalAudioStorage(), app_settings)


@router.get("/maintenance/editions")
async def preview_editions(session: SessionDep, days: DaysQuery = 90) -> dict[str, Any]:
    """Report which editions and audio files a cleanup would remove."""
    try:
        return {"data": _service(session).preview(days)}
    except Exception as exc:  # pragma: no cover - defensive boundary
        raise HTTPException(status_code=503, detail=error_body("MAINTENANCE_UNAVAILABLE", str(exc))) from exc


@router.post("/maintenance/editions")
async def clean_editions(
    session: SessionDep,
    days: DaysQuery = 90,
    dry_run: Annotated[bool, Query(description="When true, nothing is deleted")] = True,
) -> dict[str, Any]:
    """Apply the cleanup; a dry run is the default and never deletes."""
    try:
        report = await _service(session).clean(days, dry_run=dry_run)
    except Exception as exc:  # pragma: no cover - defensive boundary
        raise HTTPException(status_code=503, detail=error_body("MAINTENANCE_UNAVAILABLE", str(exc))) from exc
    report["checked_at"] = datetime.now(UTC).isoformat()
    return {"data": report}
