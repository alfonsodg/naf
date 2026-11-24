"""Measure the pilot metrics from NAF-owned rows and the reader.

The pilot in ``docs/PILOT_PLAN.md`` needs one reading per observation window.
Every number here comes from data this project owns -- ingestion runs, report
editions, and audio assets -- plus the reader's feed list. Nothing is estimated:
a value that cannot be read is ``null``, and a reader failure marks only the
source block unavailable instead of failing the whole snapshot.
"""

from datetime import UTC, datetime, timedelta
from math import ceil
from typing import Any, cast

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import Settings
from app.core.logging import get_logger
from app.core.ports.feed_reader import FeedReader
from app.models import AudioAsset, Digest, DigestStory, IngestionRun
from app.schemas.metrics import (
    AudioMetrics,
    IngestionMetrics,
    MetricsSnapshot,
    ReportMetrics,
    SourceMetrics,
)

logger = get_logger(__name__)
READER_UNAVAILABLE = "READER_UNAVAILABLE"
STALE_INTERVALS = 2


class MetricsService:
    """Build the pilot snapshot from the reader and the NAF database."""

    def __init__(self, session: Session, reader: FeedReader, settings: Settings) -> None:
        """Bind the service to storage, the reader port, and the settings."""
        self.session = session
        self.reader = reader
        self.settings = settings

    async def snapshot(self, days: int) -> MetricsSnapshot:
        """Return the metrics for the ``days`` window that ends now."""
        now = _now()
        start = now - timedelta(days=days)
        return MetricsSnapshot(
            days=days,
            generated_at=now,
            window_start=start,
            sources=await self._sources(now, start),
            ingestion=self._ingestion(start),
            reports=self._reports(start),
            audio=self._audio(start),
        )

    async def _sources(self, now: datetime, start: datetime) -> SourceMetrics:
        """Read feed freshness; a reader failure degrades only this block."""
        try:
            feeds = await self.reader.list_feeds()
        except Exception as exc:
            logger.warning("metrics source block unavailable", extra={"error": type(exc).__name__})
            return SourceMetrics(available=False, error=READER_UNAVAILABLE)

        stale_after = now - timedelta(minutes=self.settings.reader_polling_interval_minutes * STALE_INTERVALS)
        checked: list[datetime] = []
        checked_in_window = 0
        disabled = 0
        stale = 0
        parsing_errors = 0

        for feed in feeds:
            # A paused feed is deliberately not polled, so it is counted but
            # never read as stale: freshness only describes the active cohort.
            if bool(feed.get("disabled", False)):
                disabled += 1
                continue
            checked_at = _checked_at(feed.get("checked_at"))
            if checked_at is None:
                stale += 1
            else:
                checked.append(checked_at)
                if checked_at >= start:
                    checked_in_window += 1
                if checked_at < stale_after:
                    stale += 1
            if _as_int(feed.get("parsing_error_count")) > 0:
                parsing_errors += 1

        return SourceMetrics(
            available=True,
            feeds=len(feeds),
            disabled=disabled,
            checked_in_window=checked_in_window,
            stale=stale,
            parsing_errors=parsing_errors,
            newest_checked_at=max(checked) if checked else None,
            oldest_checked_at=min(checked) if checked else None,
        )

    def _ingestion(self, start: datetime) -> IngestionMetrics:
        """Count the recorded passes that started inside the window."""
        cutoff = _naive(start)
        runs = self._count_runs(cutoff)
        successes = self._count_runs(cutoff, "success")
        failures = self._count_runs(cutoff, "failed")
        running = self._count_runs(cutoff, "running")
        entries = int(
            self.session.execute(
                select(func.coalesce(func.sum(IngestionRun.entries_count), 0)).where(
                    _at_or_after(IngestionRun.started_at, cutoff)
                )
            ).scalar_one()
        )
        last = self.session.execute(
            select(IngestionRun)
            .where(_at_or_after(IngestionRun.started_at, cutoff))
            .order_by(IngestionRun.started_at.desc(), IngestionRun.id.desc())
            .limit(1)
        ).scalar_one_or_none()
        return IngestionMetrics(
            runs=runs,
            successes=successes,
            failures=failures,
            running=running,
            success_rate=_rate(successes, successes + failures),
            entries=entries,
            average_entries=_average(entries, runs),
            last_run_id=int(last.id) if last is not None else None,
            last_status=str(last.status) if last is not None and last.status is not None else None,
        )

    def _count_runs(self, cutoff: datetime, status: str | None = None) -> int:
        """Count the passes started at or after the cutoff, optionally in one state."""
        statement = select(func.count()).select_from(IngestionRun).where(_at_or_after(IngestionRun.started_at, cutoff))
        if status is not None:
            statement = statement.where(IngestionRun.status == status)
        return int(self.session.execute(statement).scalar_one())

    def _reports(self, start: datetime) -> ReportMetrics:
        """Count the stored editions and measure their size and wall time."""
        cutoff = _naive(start)
        rows = list(
            self.session.execute(
                select(Digest)
                .where(_at_or_after(Digest.created_at, cutoff))
                .options(selectinload(Digest.stories))
                .order_by(Digest.created_at.desc(), Digest.id.desc())
            )
            .scalars()
            .all()
        )
        ready = [row for row in rows if row.status == "ready"]
        included = [_entry_count(row) for row in ready]
        latencies = [value for row in ready if (value := _latency(row)) is not None]
        return ReportMetrics(
            editions=len(rows),
            ready=len(ready),
            no_news=sum(1 for row in rows if row.status == "no_news"),
            failed=sum(1 for row in rows if row.status == "failed"),
            average_included_entries=_average(sum(included), len(included)),
            p50_seconds=_percentile(latencies, 0.50),
            p95_seconds=_percentile(latencies, 0.95),
        )

    def _audio(self, start: datetime) -> AudioMetrics:
        """Sum the audio assets stored inside the window."""
        cutoff = _naive(start)
        assets = list(
            self.session.execute(select(AudioAsset).where(_at_or_after(AudioAsset.created_at, cutoff))).scalars().all()
        )
        durations = [float(cast(float | None, asset.duration_seconds) or 0.0) for asset in assets]
        sizes = [_as_int(asset.size_bytes) for asset in assets]
        editions = {int(cast(int, asset.digest_id)) for asset in assets if asset.digest_id is not None}
        return AudioMetrics(
            assets=len(assets),
            duration_seconds=round(sum(durations), 3),
            size_bytes=sum(sizes),
            editions_with_audio=len(editions),
        )


def _entry_count(row: Digest) -> int:
    """Read the number of entries one edition included."""
    entry_ids: list[Any] = row.entry_ids if isinstance(row.entry_ids, list) else []
    return len(entry_ids)


def _latency(row: Digest) -> float | None:
    """Return the wall time from edition creation to its newest story or update."""
    created = cast(datetime | None, row.created_at)
    updated = cast(datetime | None, row.updated_at)
    if created is None:
        return None

    newest = updated
    stories: list[DigestStory] = cast(list[DigestStory], row.stories)
    for story in stories:
        story_created = cast(datetime | None, story.created_at)
        if story_created is not None and (newest is None or story_created > newest):
            newest = story_created
    if newest is None or newest < created:
        return None
    return (newest - created).total_seconds()


def _checked_at(value: Any) -> datetime | None:
    """Read a reader check instant as aware UTC, or None when absent."""
    if isinstance(value, datetime):
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    if isinstance(value, int | float):
        return datetime.fromtimestamp(value, UTC)
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)


def _at_or_after(column: Any, cutoff: datetime) -> ColumnElement[bool]:
    """Compare a column with a cutoff; the models declare their columns untyped."""
    return cast(ColumnElement[bool], column >= cutoff)


def _as_int(value: Any) -> int:
    """Read an optional counter as an integer, treating junk as zero."""
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    try:
        return int(value) if value is not None else 0
    except (TypeError, ValueError):
        return 0


def _rate(numerator: int, denominator: int) -> float | None:
    """Return a 0-1 rate rounded for a stable contract, or None without a denominator."""
    return round(numerator / denominator, 4) if denominator else None


def _average(total: float, count: int) -> float | None:
    """Return a rounded average, or None when there is nothing to average."""
    return round(total / count, 4) if count else None


def _percentile(values: list[float], fraction: float) -> float | None:
    """Return a nearest-rank percentile, or None when no value was measured."""
    if not values:
        return None
    ordered = sorted(values)
    index = max(1, ceil(fraction * len(ordered))) - 1
    return round(ordered[index], 3)


def _now() -> datetime:
    """Return the current instant as aware UTC."""
    return datetime.now(UTC)


def _naive(value: datetime) -> datetime:
    """Store the instant in the naive UTC form the columns use."""
    return value.astimezone(UTC).replace(tzinfo=None)
