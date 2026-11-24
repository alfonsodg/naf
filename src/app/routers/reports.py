"""Report API: generate on demand, list the history, and read one edition."""

from importlib import import_module
from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response
from sqlalchemy.orm import Session

from app.adapters.miniflux.client import MinifluxClient
from app.adapters.storage.local import LocalAudioStorage
from app.core.config import settings as app_settings
from app.core.exceptions import CitationValidationError, MinifluxAPIError, ReportGenerationError, TTSError
from app.core.ports.feed_reader import FeedReader
from app.core.ports.report_generator import ReportGenerator
from app.core.ports.storage import AudioStorage
from app.core.ports.tts import TTSProvider
from app.db.session import get_session
from app.routers.feeds import LimitQuery, PageQuery
from app.schemas.errors import error_body
from app.schemas.reports import (
    AudioAssetResponse,
    AudioAssetView,
    ReportCreateRequest,
    ReportDetail,
    ReportDetailResponse,
    ReportListResponse,
    ReportPagination,
    ReportResponse,
    ReportSummary,
)
from app.services.audio import AudioService
from app.services.reporting import ReportService

router = APIRouter()

SessionDep = Annotated[Session, Depends(get_session)]
ForceQuery = Annotated[bool, Query(description="Synthesize again even when the edition already has an asset")]


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


def _tts() -> TTSProvider:
    """Build the configured speech engine through the Kokoro adapter.

    Resolved on demand for the same reason as the generator: the package is an
    optional extra, and the API starts without it.
    """
    try:
        module = import_module("app.adapters.tts.kokoro")
    except ImportError as exc:
        raise HTTPException(
            status_code=503,
            detail=error_body("TTS_NOT_CONFIGURED", "no speech adapter is installed"),
        ) from exc
    factory: Any = cast(Any, module).KokoroTTS
    return cast(TTSProvider, factory(app_settings))


def _audio_storage() -> AudioStorage:
    """Build the local audio storage adapter for one request."""
    return cast(AudioStorage, LocalAudioStorage())


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
    detail.audio.sort(key=lambda asset: asset.asset_id)
    return ReportDetailResponse(data=detail)


@router.post("/reports/{report_id}/audio", status_code=201)
async def create_report_audio(
    report_id: Annotated[int, Path(ge=1)],
    session: SessionDep,
    force: ForceQuery = False,
) -> AudioAssetResponse:
    """Synthesize and store the spoken edition of one ready report.

    The engine configuration is checked before anything else, so an
    unconfigured deployment never reads the edition, calls the engine, or
    writes a file. A report that is not ready cannot be voiced: its text is a
    placeholder or a stored failure, not a report. An existing asset is served
    unchanged unless ``force`` asks for a regeneration.
    """
    if not app_settings.tts_model_path or not app_settings.tts_voices_path:
        raise HTTPException(
            status_code=503,
            detail=error_body("TTS_NOT_CONFIGURED", "no speech model or voices file is configured"),
        )
    digest = ReportService.get_report(session, report_id)
    if digest is None:
        raise HTTPException(
            status_code=404,
            detail=error_body("REPORT_NOT_FOUND", f"no report was recorded with identifier {report_id}"),
        )
    if digest.status != "ready":
        raise HTTPException(
            status_code=409,
            detail=error_body(
                "REPORT_NOT_READY",
                f"report {report_id} is {digest.status} and cannot be voiced",
                [{"status": digest.status}],
            ),
        )
    service = AudioService(session, _tts(), _audio_storage(), app_settings)
    try:
        asset = await service.generate(digest, force=force)
    except TTSError as exc:
        raise HTTPException(
            status_code=502,
            detail=error_body("TTS_SYNTHESIS_FAILED", "the spoken edition could not be generated"),
        ) from exc
    return AudioAssetResponse(data=AudioAssetView.model_validate(asset))


@router.get("/reports/{report_id}/audio")
async def read_report_audio(report_id: Annotated[int, Path(ge=1)], session: SessionDep) -> Response:
    """Serve the newest WAV asset stored for one report."""
    digest = ReportService.get_report(session, report_id)
    if digest is None:
        raise HTTPException(
            status_code=404,
            detail=error_body("REPORT_NOT_FOUND", f"no report was recorded with identifier {report_id}"),
        )
    asset = AudioService.latest_asset(session, report_id)
    if asset is None:
        raise HTTPException(
            status_code=404,
            detail=error_body("AUDIO_NOT_FOUND", f"report {report_id} has no stored audio"),
        )
    try:
        audio = await _audio_storage().retrieve(cast(str, asset.file_path))
    except OSError as exc:
        raise HTTPException(
            status_code=404,
            detail=error_body("AUDIO_NOT_FOUND", "the stored audio file is no longer available"),
        ) from exc
    return Response(
        content=audio,
        media_type="audio/wav",
        headers={"Content-Disposition": f'attachment; filename="{asset.filename}"'},
    )
