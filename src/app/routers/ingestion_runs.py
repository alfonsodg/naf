"""Ingestion run history: what every recorded pass saw and what failed."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.routers.feeds import LimitQuery, PageQuery
from app.schemas.errors import error_body
from app.schemas.ingestion import (
    IngestionRunDetailResponse,
    IngestionRunListResponse,
    IngestionRunPagination,
    IngestionRunResponse,
    IngestionRunStatus,
)
from app.services.ingestion_runs import IngestionRunStore

router = APIRouter()

SessionDep = Annotated[Session, Depends(get_session)]


@router.get("/ingestion-runs")
async def list_ingestion_runs(
    session: SessionDep,
    page: PageQuery = 1,
    per_page: LimitQuery = 50,
    status: IngestionRunStatus | None = None,
) -> IngestionRunListResponse:
    """List the recorded ingestion runs, newest first, with pagination metadata.

    ``status`` narrows the history to the runs in one state, so a caller can
    list the failed passes without reading a page of successful ones.
    """
    runs, total = IngestionRunStore(session).list_runs(
        limit=per_page,
        offset=(page - 1) * per_page,
        status=status,
    )
    return IngestionRunListResponse(
        data=[IngestionRunResponse.model_validate(run) for run in runs],
        pagination=IngestionRunPagination(
            page=page,
            per_page=per_page,
            total=total,
            total_pages=(total + per_page - 1) // per_page if total else 0,
        ),
    )


@router.get("/ingestion-runs/{run_id}")
async def read_ingestion_run(run_id: Annotated[int, Path(ge=1)], session: SessionDep) -> IngestionRunDetailResponse:
    """Return one recorded pass with its per-feed errors and its summary.

    A run left in ``running`` is served as it was recorded: the status differs
    and ``finished_at`` is absent, so an open pass is never read as a failure.
    """
    run = IngestionRunStore(session).get_run(run_id)
    if run is None:
        raise HTTPException(
            status_code=404,
            detail=error_body(
                "INGESTION_RUN_NOT_FOUND",
                f"no ingestion run was recorded with identifier {run_id}",
            ),
        )
    return IngestionRunDetailResponse(data=IngestionRunResponse.model_validate(run))
