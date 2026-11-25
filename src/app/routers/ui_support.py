"""View helpers shared by the server-rendered pages.

The templates, the form parser, the Spanish labels, and the segment
normalization live here so the router only declares routes. Nothing in this
module talks to Miniflux, a model, or the speech engine: it receives the stored
rows and the values the user typed.
"""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import Request
from fastapi.responses import Response
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy.orm import Session
from starlette.datastructures import FormData

from app.core.config import settings as app_settings
from app.core.logging import get_logger
from app.models import Digest
from app.schemas.reports import ReportCreateRequest, ReportStory, ReportSummary
from app.services.audio import AudioService
from app.services.reporting import ReportService

ASSET_DIR = Path(__file__).resolve().parent.parent
STATUS_LABELS = {"draft": "Borrador", "ready": "Listo", "no_news": "Sin novedades", "failed": "Fallido"}
FORM_FIELDS = ("period_start", "period_end", "max_entries", "tags", "search", "since_last")
HISTORY_LIMIT = 50
BATCH_MAX_LIMIT = 20
FALLBACK_TIMEZONE = "UTC"

logger = get_logger(__name__)
templates = Jinja2Templates(directory=str(ASSET_DIR / "templates"))


class FormError(Exception):
    """A form value the user can correct without losing the rest of the input."""


def render(request: Request, name: str, context: dict[str, Any], status_code: int = 200) -> Response:
    """Render one template with the Spanish status labels every page may use."""
    return templates.TemplateResponse(
        request,
        name,
        {**context, "status_labels": STATUS_LABELS},
        status_code=status_code,
    )


def not_found(request: Request, message: str) -> Response:
    """Render the Spanish 404 page."""
    return render(request, "error.html", {"title": "Informe no encontrado", "message": message}, status_code=404)


def history(session: Session) -> list[ReportSummary]:
    """Project the newest editions onto the summary shape the history lists."""
    rows, _total = ReportService.list_reports(session, 1, HISTORY_LIMIT)
    return [ReportSummary.model_validate(row) for row in rows]


def index_context(
    session: Session,
    form: dict[str, str],
    error: str | None = None,
    notice: str | None = None,
) -> dict[str, Any]:
    """Build the context shared by the first render and a re-rendered form."""
    return {"reports": history(session), "form": form, "error": error, "notice": notice}


def empty_form() -> dict[str, str]:
    """Return the creation form with every field empty."""
    return dict.fromkeys(FORM_FIELDS, "")


def form_state(form: FormData) -> dict[str, str]:
    """Keep what the user typed so a rejected form is not empty again."""
    state = empty_form()
    for name in state:
        state[name] = field(form, name)
    state["since_last"] = "1" if checked(form, "since_last") else ""
    return state


def field(form: FormData, name: str) -> str:
    """Read one text field, ignoring an uploaded file with the same name."""
    value = form.get(name)
    return value.strip() if isinstance(value, str) else ""


def checked(form: FormData, name: str) -> bool:
    """Report whether a checkbox was submitted."""
    return form.get(name) is not None


def parse_request(form: FormData) -> ReportCreateRequest:
    """Translate the Spanish form into the request the report service consumes."""
    start = instant(field(form, "period_start"))
    end = instant(field(form, "period_end"))
    if (start is None) != (end is None):
        raise FormError("Indica las dos fechas del periodo o ninguna.")
    tags = [tag.strip() for tag in field(form, "tags").split(",") if tag.strip()] or None
    try:
        return ReportCreateRequest(
            period_start=start,
            period_end=end,
            since_last=checked(form, "since_last"),
            tags=tags,
            search=field(form, "search") or None,
            max_entries=max_entries(field(form, "max_entries")),
        )
    except ValidationError as exc:
        raise FormError("La fecha de inicio no puede ser posterior a la de fin.") from exc


def instant(value: str) -> datetime | None:
    """Read a datetime-local field as aware UTC, or nothing when it is empty."""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise FormError("Revisa el formato de las fechas del periodo.") from exc
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)


def max_entries(value: str) -> int | None:
    """Read the optional selection size, naming the field when it is wrong."""
    if not value:
        return None
    try:
        limit = int(value)
    except ValueError as exc:
        raise FormError("El máximo de entradas debe ser un número entero.") from exc
    if limit < 1:
        raise FormError("El máximo de entradas debe ser al menos 1.")
    return limit


def batch_limit(value: str) -> int:
    """Read how many pending entries to classify, bounded by the batch contract."""
    try:
        limit = int(value)
    except ValueError as exc:
        raise FormError(f"Indica cuántas novedades clasificar, entre 1 y {BATCH_MAX_LIMIT}.") from exc
    if not 1 <= limit <= BATCH_MAX_LIMIT:
        raise FormError(f"La cantidad de novedades debe estar entre 1 y {BATCH_MAX_LIMIT}.")
    return limit


def stored_segments(session: Session, report_id: int) -> object:
    """Read the segment list stored with the newest asset of one edition."""
    asset = AudioService.latest_asset(session, report_id)
    return None if asset is None else cast(object, getattr(asset, "segments", None))


def segments(value: object, stories: list[ReportStory]) -> list[dict[str, Any]]:
    """Normalize the stored segments and attach the citations of their story."""
    if not isinstance(value, list):
        return []
    result: list[dict[str, Any]] = []
    for position, raw in enumerate(value):
        if not isinstance(raw, dict):
            continue
        stored = raw.get("story_index")
        index = (
            stored if isinstance(stored, int) and not isinstance(stored, bool) and 0 <= stored < len(stories) else None
        )
        story = stories[index] if index is not None else None
        result.append(
            {
                "index": _as_int(raw.get("index"), position),
                "start_seconds": _as_float(raw.get("start_seconds")),
                "end_seconds": _as_float(raw.get("end_seconds")),
                "text": str(raw.get("text") or "").strip(),
                "story_index": index,
                "citations": [] if story is None else [citation.model_dump() for citation in story.citations],
            }
        )
    return result


def display_zone(name: str | None = None) -> ZoneInfo:
    """Resolve the configured IANA zone, falling back to UTC with a warning."""
    candidate = name or app_settings.display_timezone or FALLBACK_TIMEZONE
    try:
        return ZoneInfo(candidate)
    except (ZoneInfoNotFoundError, ValueError):
        logger.warning("unknown display timezone; using UTC", extra={"timezone": candidate})
        return ZoneInfo(FALLBACK_TIMEZONE)


def format_instant(value: datetime | None, timezone: str | None = None) -> str:
    """Render a stored UTC instant in the display zone, naming the offset used."""
    if value is None:
        return "Sin datos"
    moment = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    local = moment.astimezone(display_zone(timezone))
    return local.strftime("%d/%m/%Y %H:%M") + f" {local.tzname() or FALLBACK_TIMEZONE}"


def format_seconds(value: float) -> str:
    """Render a playback position as minutes and seconds."""
    total = max(0, int(value))
    return f"{total // 60:02d}:{total % 60:02d}"


def _as_int(value: object, fallback: int) -> int:
    """Read a stored integer, falling back to the segment position."""
    return value if isinstance(value, int) and not isinstance(value, bool) else fallback


def _as_float(value: object) -> float:
    """Read a stored instant in seconds, reading a missing value as zero."""
    return float(value) if isinstance(value, int | float) and not isinstance(value, bool) else 0.0


def report_id(row: Digest) -> int:
    """Read the stored identifier as an integer for a redirect."""
    return cast(int, row.id)


templates.env.filters["instant"] = format_instant
templates.env.filters["mmss"] = format_seconds
