"""Shared fixtures for the metrics suite: settings, a reader double, and seeds.

The helpers live outside the test module so every metrics test stays under the
file-size limit while seeding the same reproducible rows.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models import AudioAsset, Digest, DigestStory, IngestionRun


def settings(**overrides: Any) -> Settings:
    """Build settings with the deployment values a test does not care about."""
    base: dict[str, Any] = {
        "database_url": "postgresql://test:test@localhost:5432/naf_test",
        "miniflux_url": "http://localhost:8080",
        "miniflux_api_key": "test-token",
        "reader_polling_interval_minutes": 20,
        **overrides,
    }
    return Settings(**base)


def db(value: datetime) -> datetime:
    """Convert an aware instant to the naive UTC form the columns store."""
    return value.astimezone(UTC).replace(tzinfo=None)


def instant(value: str) -> datetime:
    """Read one instant returned by the API as aware UTC."""
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class FakeReader:
    """Reader double that returns a fixed feed list or raises on demand."""

    def __init__(self, feeds: list[dict[str, Any]] | None = None, error: Exception | None = None) -> None:
        self.feeds = feeds or []
        self.error = error

    async def list_feeds(self) -> list[dict[str, Any]]:
        """Return the configured feed list, or the configured failure."""
        if self.error is not None:
            raise self.error
        return self.feeds


def run(session: Session, started: datetime, status: str, entries: int) -> int:
    """Store one ingestion pass and return its identifier."""
    row = IngestionRun(
        adapter_name="miniflux",
        started_at=db(started),
        finished_at=None if status == "running" else db(started + timedelta(minutes=1)),
        status=status,
        entries_count=entries,
        errors=[],
    )
    session.add(row)
    session.flush()
    return int(row.id)


def digest(
    session: Session,
    created: datetime,
    status: str = "ready",
    entry_ids: list[int] | None = None,
    latency_seconds: int | None = None,
) -> Digest:
    """Store one report edition, optionally with one story that fixes its wall time."""
    row = Digest(
        title="Radar semanal",
        summary="Resumen del periodo.",
        period_start=db(created - timedelta(days=1)),
        period_end=db(created),
        filters={},
        entry_ids=entry_ids or [],
        version="1.0",
        meta={},
        status=status,
        created_at=db(created),
        updated_at=db(created),
    )
    if latency_seconds is not None:
        row.stories = [
            DigestStory(
                title="Historia uno",
                summary="Resumen de la historia.",
                claims=[],
                citations=[],
                order_index=0,
                created_at=db(created + timedelta(seconds=latency_seconds)),
            )
        ]
    session.add(row)
    session.flush()
    return row


def audio(session: Session, report: Digest, created: datetime, duration: float, size: int) -> None:
    """Store one audio asset for an edition."""
    session.add(
        AudioAsset(
            digest_id=report.id,
            filename=f"report-{report.id}.wav",
            file_path=f"/audio/report-{report.id}.wav",
            duration_seconds=duration,
            size_bytes=size,
            created_at=db(created),
        )
    )
