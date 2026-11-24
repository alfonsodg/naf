"""Report API: generate on demand, list the history, and read one edition."""

from importlib import import_module
from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session

from app.adapters.miniflux.client import MinifluxClient
from app.core.config import settings as app_settings
from app.core.exceptions import CitationValidationError, MinifluxAPIError, ReportGenerationError
from app.core.ports.feed_reader import FeedReader
from app.core.ports.report_generator import ReportGenerator
from app.db.session import get_session
from app.routers.feeds import LimitQuery, PageQuery
from app.schemas.errors import error_body
from app.schemas.reports import (
    ReportCreateRequest,
    ReportDetail,
    ReportDetailResponse,
    ReportListResponse,
    ReportPagination,
    ReportResponse,
    ReportSummary,
)
from app.services.reporting import ReportService

router = APIRouter()

SessionDep = Annotated[Session, Depends(get_session)]


def _reader() -> FeedReader:
    """Build the reader adapter for one request."""
    return MinifluxClient()


def _generator() -> ReportGenerator:
    """Build the configured generator through the LLM adapter.

    The adapter is resolved on demand, not at import time: the API starts
    without a provider, and an unconfigured deployment answers 503 instead of
    failing at boot.
    """
    try:
        module = import_module("app.adapters.llm.openai_report")
    except ImportError as exc:
        raise HTTPException(
            status_code=503,
            detail=error_body("REPORT_GENERATOR_NOT_CONFIGURED", "no report generator adapter is installed"),
        ) from exc
    factory: Any = cast(Any, module).OpenAIReportGenerator
    return cast(ReportGenerator, factory(app_settings))


@router.post("/reports", status_code=201)
async def create_report(payload: ReportCreateRequest, session: SessionDep) -> ReportResponse:
    """Generate one report over the requested selection and store the edition.

    An unconfigured model is refused before the reader is touched. A generation
    failure is stored with its reason and answered as 502; the provider detail
    and the API key never reach the caller.
    """
    if not app_settings.llm_model:
        raise HTTPException(
            status_code=503,
            detail=error_body("REPORT_GENERATOR_NOT_CONFIGURED", "no LLM model is configured for report generation"),
        )

    service = ReportService(session, _reader(), _generator(), app_settings)
    try:
        report = await service.create(payload)
    except MinifluxAPIError as exc:
        raise HTTPException(status_code=502, detail=error_body("MINIFLUX_UNAVAILABLE", str(exc))) from exc
    except CitationValidationError as exc:
        raise HTTPException(
            status_code=502,
            detail=error_body(
                "REPORT_CITATIONS_INVALID",
                "the generated report makes a claim without a source entry in the selection",
            ),
        ) from exc
    except ReportGenerationError as exc:
        raise HTTPException(
            status_code=502,
            detail=error_body(
                "REPORT_GENERATION_FAILED", "the report could not be generated; the edition keeps the reason"
            ),
        ) from exc
    return ReportResponse(data=ReportSummary.model_validate(report))


@router.get("/reports")
async def list_reports(
    session: SessionDep,
    page: PageQuery = 1,
    per_page: LimitQuery = 50,
) -> ReportListResponse:
    """List the stored editions, newest first, with pagination metadata."""
    rows, total = ReportService.list_reports(session, page, per_page)
    return ReportListResponse(
        data=[ReportSummary.model_validate(row) for row in rows],
        pagination=ReportPagination(
            page=page,
            per_page=per_page,
            total=total,
            total_pages=(total + per_page - 1) // per_page if total else 0,
        ),
    )


@router.get("/reports/{report_id}")
async def read_report(report_id: Annotated[int, Path(ge=1)], session: SessionDep) -> ReportDetailResponse:
    """Return one stored edition with its stories, claims, and citations."""
    row = ReportService.get_report(session, report_id)
    if row is None:
        raise HTTPException(
            status_code=404,
            detail=error_body("REPORT_NOT_FOUND", f"no report was recorded with identifier {report_id}"),
        )
    detail = ReportDetail.model_validate(row)
    detail.stories.sort(key=lambda story: story.order_index)
    return ReportDetailResponse(data=detail)
