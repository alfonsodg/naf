"""Server-rendered interface: create a report, read it, play it, and list sources.

The pages are served by the same process as the versioned API and never talk to
Miniflux directly from the browser: the reader, the generator, and the speech
engine are reached through the same ports the API uses. User-facing text is
Spanish; the code stays English.
"""

from importlib import import_module
from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse, Response
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
from app.routers.ui_support import (
    FormError,
    empty_form,
    form_state,
    index_context,
    not_found,
    parse_request,
    render,
    report_id,
    segments,
    stored_segments,
)
from app.schemas.reports import ReportDetail
from app.services.audio import AudioService
from app.services.collector import normalize_feed
from app.services.reporting import ReportService

router = APIRouter()
SessionDep = Annotated[Session, Depends(get_session)]

NOTICES = {"audio": "El audio del informe está disponible."}
ERRORS = {
    "tts": "No se pudo generar el audio. El informe de texto sigue disponible y puedes volver a intentarlo.",
    "tts-config": "La síntesis de voz no está configurada en este despliegue.",
    "not-ready": "Solo un informe listo puede convertirse en audio.",
}
GENERATION_ERROR = "No se pudo generar el informe. Inténtalo de nuevo más tarde."
READER_ERROR = "No se pudo consultar el lector de fuentes. Comprueba que Miniflux esté disponible."
CITATIONS_ERROR = "El informe generado no tiene una fuente válida para cada afirmación. No se ha publicado."


def _reader() -> FeedReader:
    """Build the reader adapter for one request."""
    return MinifluxClient()


def _generator() -> ReportGenerator:
    """Resolve the configured generator, refusing an unconfigured deployment."""
    try:
        module = import_module("app.adapters.llm.openai_report")
    except ImportError as exc:
        raise ReportGenerationError("no report generator adapter is installed") from exc
    factory: Any = cast(Any, module).OpenAIReportGenerator
    return cast(ReportGenerator, factory(app_settings))


def _tts() -> TTSProvider:
    """Resolve the configured speech engine, refusing an uninstalled extra."""
    try:
        module = import_module("app.adapters.tts.kokoro")
    except ImportError as exc:
        raise TTSError("no speech adapter is installed") from exc
    factory: Any = cast(Any, module).KokoroTTS
    return cast(TTSProvider, factory(app_settings))


def _audio_storage() -> AudioStorage:
    """Build the local audio storage adapter for one request."""
    return cast(AudioStorage, LocalAudioStorage())


def _query_message(request: Request) -> tuple[str | None, str | None]:
    """Translate the fixed notice and error codes a redirect may carry."""
    return NOTICES.get(request.query_params.get("notice", "")), ERRORS.get(request.query_params.get("error", ""))


@router.get("/", response_model=None)
async def index(request: Request, session: SessionDep) -> Response:
    """Show the report history and the creation form."""
    notice, error = _query_message(request)
    return render(request, "index.html", index_context(session, empty_form(), error=error, notice=notice))


@router.post("/ui/reports", response_model=None)
async def create_report(request: Request, session: SessionDep) -> Response:
    """Generate one report from the form and redirect to its edition."""
    form = await request.form()
    state = form_state(form)
    try:
        payload = parse_request(form)
    except FormError as exc:
        return render(request, "index.html", index_context(session, state, error=str(exc)), status_code=400)
    if not app_settings.llm_model:
        message = "El generador de informes no está configurado; la historia sigue disponible."
        return render(request, "index.html", index_context(session, state, error=message), status_code=503)
    try:
        report = await ReportService(session, _reader(), _generator(), app_settings).create(payload)
    except MinifluxAPIError:
        return render(request, "index.html", index_context(session, state, error=READER_ERROR), status_code=502)
    except CitationValidationError:
        return render(request, "index.html", index_context(session, state, error=CITATIONS_ERROR), status_code=502)
    except (ReportGenerationError, ImportError):
        return render(request, "index.html", index_context(session, state, error=GENERATION_ERROR), status_code=502)
    return RedirectResponse(f"/reports/{report_id(report)}", status_code=303)


@router.get("/reports/{report_id}", response_model=None)
async def read_report(report_id: int, request: Request, session: SessionDep) -> Response:
    """Render one edition with its stories, citations, audio, and transcript."""
    row = ReportService.get_report(session, report_id)
    if row is None:
        return not_found(request, "No existe ningún informe con ese identificador.")
    detail = ReportDetail.model_validate(row)
    detail.stories.sort(key=lambda story: story.order_index)
    detail.audio.sort(key=lambda asset: asset.asset_id)
    asset = detail.audio[-1] if detail.audio else None
    notice, error = _query_message(request)
    return render(
        request,
        "report.html",
        {
            "report": detail,
            "asset": asset,
            "segments": segments(stored_segments(session, report_id), detail.stories),
            "notice": notice,
            "error": error,
        },
    )


@router.post("/ui/reports/{report_id}/audio", response_model=None)
async def generate_audio(report_id: int, request: Request, session: SessionDep) -> Response:
    """Synthesize the edition and return to it with a recoverable notice."""
    row = ReportService.get_report(session, report_id)
    if row is None:
        return not_found(request, "No existe ningún informe con ese identificador.")
    if not app_settings.tts_model_path or not app_settings.tts_voices_path:
        return _redirect(report_id, "error=tts-config")
    if row.status != "ready":
        return _redirect(report_id, "error=not-ready")
    try:
        await AudioService(session, _tts(), _audio_storage(), app_settings).generate(row)
    except TTSError:
        return _redirect(report_id, "error=tts")
    return _redirect(report_id, "notice=audio")


@router.get("/sources", response_model=None)
async def sources(request: Request) -> Response:
    """List the configured feeds with their category and last check."""
    try:
        feeds = [normalize_feed(feed) for feed in await _reader().list_feeds()]
    except MinifluxAPIError:
        return render(request, "sources.html", {"feeds": [], "error": READER_ERROR}, status_code=502)
    return render(request, "sources.html", {"feeds": feeds, "error": None})


def _redirect(report_id: int, query: str) -> RedirectResponse:
    """Return to the edition carrying one fixed notice or error code."""
    return RedirectResponse(f"/reports/{report_id}?{query}", status_code=303)
