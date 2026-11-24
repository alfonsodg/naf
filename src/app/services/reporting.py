"""Generate one report on demand and read the stored editions back.

The reader owns the entries, the generator owns the text, and NAF owns the
record: the selection it used, the entries it included, the cursor it reached,
and the failure it hit. A report is persisted before the caller sees the result,
so a generation error is recoverable and a repeated request never duplicates an
edition silently.
"""

from datetime import UTC, datetime, timedelta
from typing import Any, NamedTuple

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.exceptions import CitationValidationError, ReportGenerationError
from app.core.ports.feed_reader import FeedReader
from app.core.ports.report_generator import ReportGenerator
from app.models import Digest, DigestStory
from app.schemas.digest import Digest as GeneratedDigest
from app.schemas.reports import ReportCreateRequest
from app.services.report_selection import published_at, select_entries, utc

PROMPT_VERSION = "1.1"
NO_NEWS_TITLE = "Sin novedades"
NO_NEWS_SUMMARY = "No hay entradas nuevas en el periodo solicitado. No se reutiliza contenido de informes anteriores."
FAILED_TITLE = "Informe no generado"
FAILED_SUMMARY = "No se pudo generar el informe solicitado. La edición conserva el error para revisarlo."


class Period(NamedTuple):
    """Resolved selection window and the cursor a since-last request used."""

    start: datetime
    end: datetime
    cursor: str | None


class ReportService:
    """Select entries, ask for a cited report, and persist the outcome."""

    def __init__(self, session: Session, reader: FeedReader, generator: ReportGenerator, settings: Settings) -> None:
        """Bind the service to storage, the reader port, the generator port, and the settings."""
        self.session = session
        self.reader = reader
        self.generator = generator
        self.settings = settings

    async def create(self, request: ReportCreateRequest) -> Digest:
        """Build one report and return the stored edition.

        An empty selection is stored as ``no_news`` without calling the model.
        A generator or citation failure is stored as ``failed`` and re-raised,
        so the caller answers 502 while the edition keeps the reason.
        """
        period = self._period(request)
        filters = _filters(request)
        limit = min(request.max_entries or self.settings.report_max_entries, self.settings.report_max_entries)
        entries = await select_entries(self.reader, request, period.start, period.end, limit)
        if not entries:
            return self._store_no_news(period, filters)
        try:
            generated = await self.generator.generate(entries, filters, period.cursor)
            if not self.generator.validate_citations(generated, entries):
                raise CitationValidationError("the report carries a claim with no source entry")
        except (ReportGenerationError, CitationValidationError) as exc:
            self._store_failed(period, filters, entries, exc)
            raise
        return self._store_ready(period, filters, entries, generated)

    @classmethod
    def list_reports(cls, session: Session, page: int, per_page: int) -> tuple[list[Digest], int]:
        """Return one page of the stored editions, newest first, and the total count.

        Reads need neither the reader nor the generator, so the history stays
        available while the model is unconfigured.
        """
        offset = (page - 1) * per_page
        statement = select(Digest).order_by(Digest.created_at.desc(), Digest.id.desc()).limit(per_page).offset(offset)
        rows = session.execute(statement).scalars().all()
        total = session.execute(select(func.count()).select_from(Digest)).scalar_one()
        return list(rows), int(total)

    @classmethod
    def get_report(cls, session: Session, report_id: int) -> Digest | None:
        """Return one stored edition with its stories, or None when the identifier is unknown."""
        return session.get(Digest, report_id)

    def _period(self, request: ReportCreateRequest) -> Period:
        """Resolve the selection window from the cursor, the request, or the default window."""
        now = _now()
        if request.since_last:
            cursor = self._last_cursor()
            start = _parse_cursor(cursor) if cursor is not None else None
            if cursor is not None and start is not None:
                return Period(start, now, cursor)
            return Period(now - timedelta(days=self.settings.report_default_days), now, None)
        if request.period_start is not None and request.period_end is not None:
            return Period(utc(request.period_start), utc(request.period_end), None)
        return Period(now - timedelta(days=self.settings.report_default_days), now, None)

    def _last_cursor(self) -> str | None:
        """Return the newest recorded cursor, skipping editions that never reached one."""
        row = self.session.execute(
            select(Digest.cursor)
            .where(Digest.cursor.is_not(None))
            .order_by(Digest.created_at.desc(), Digest.id.desc())
            .limit(1)
        ).scalar_one_or_none()
        return row if isinstance(row, str) and row else None

    def _store_no_news(self, period: Period, filters: dict[str, Any]) -> Digest:
        """Persist the explicit Spanish no-news edition without calling the generator."""
        return self._store(
            Digest(
                title=NO_NEWS_TITLE,
                summary=NO_NEWS_SUMMARY,
                period_start=_naive(period.start),
                period_end=_naive(period.end),
                filters=filters,
                entry_ids=[],
                cursor=None,
                version=PROMPT_VERSION,
                meta=self._meta(0),
                status="no_news",
            )
        )

    def _store_ready(
        self,
        period: Period,
        filters: dict[str, Any],
        entries: list[dict[str, Any]],
        generated: GeneratedDigest,
    ) -> Digest:
        """Persist a generated edition with its stories, claims, and citations."""
        newest = published_at(entries[0]) if entries else None
        row = Digest(
            title=generated.title,
            summary=generated.summary,
            period_start=_naive(period.start),
            period_end=_naive(period.end),
            filters=filters,
            entry_ids=_entry_ids(entries),
            cursor=newest.isoformat() if newest is not None else None,
            version=generated.version,
            meta=self._meta(len(entries)),
            status="ready",
        )
        row.stories = [
            DigestStory(
                title=story.title,
                summary=story.summary,
                claims=story.claims,
                citations=[citation.model_dump() for citation in story.citations],
                pub_type=story.pub_type,
                official=story.official,
                uncertainties=story.uncertainties,
                entities=story.entities,
                order_index=index,
            )
            for index, story in enumerate(generated.stories)
        ]
        return self._store(row)

    def _store_failed(
        self,
        period: Period,
        filters: dict[str, Any],
        entries: list[dict[str, Any]],
        exc: Exception,
    ) -> Digest:
        """Persist the failed edition with a redacted reason, then let the caller answer 502."""
        return self._store(
            Digest(
                title=FAILED_TITLE,
                summary=FAILED_SUMMARY,
                period_start=_naive(period.start),
                period_end=_naive(period.end),
                filters=filters,
                entry_ids=_entry_ids(entries),
                cursor=None,
                version=PROMPT_VERSION,
                meta=self._meta(len(entries)),
                status="failed",
                error_summary=_redact(str(exc), self.settings.llm_api_key),
            )
        )

    def _store(self, row: Digest) -> Digest:
        """Store one edition and return it with its identifier."""
        self.session.add(row)
        self.session.commit()
        return row

    def _meta(self, entry_count: int) -> dict[str, Any]:
        """Describe the generator that produced, or was meant to produce, the edition."""
        return {
            "model": self.settings.llm_model,
            "prompt_version": PROMPT_VERSION,
            "entry_count": entry_count,
        }


def _filters(request: ReportCreateRequest) -> dict[str, Any]:
    """Record the effective request filters for reproducibility."""
    return {
        "feed_ids": request.feed_ids,
        "category_ids": request.category_ids,
        "tags": request.tags,
        "search": request.search,
        "read": request.read,
        "starred": request.starred,
        "since_last": request.since_last,
        "max_entries": request.max_entries,
    }


def _entry_ids(entries: list[dict[str, Any]]) -> list[int]:
    """Keep the reader identifiers a stored edition formally included."""
    return [entry["entry_id"] for entry in entries if isinstance(entry.get("entry_id"), int)]


def _parse_cursor(cursor: str) -> datetime | None:
    """Read a stored ISO-8601 cursor as aware UTC."""
    try:
        return utc(datetime.fromisoformat(cursor.replace("Z", "+00:00")))
    except ValueError:
        return None


def _redact(message: str, secret: str) -> str:
    """Keep the provider reason while never storing the configured key."""
    redacted = message.replace(secret, "***") if secret else message
    return redacted.strip() or "the generator reported a failure"


def _now() -> datetime:
    """Return the current instant as aware UTC."""
    return datetime.now(UTC)


def _naive(value: datetime) -> datetime:
    """Store the instant in the naive UTC form the columns use."""
    return utc(value).replace(tzinfo=None)
