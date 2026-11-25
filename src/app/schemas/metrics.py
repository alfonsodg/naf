"""Response shape for the pilot metrics snapshot.

The pilot in ``docs/PILOT_PLAN.md`` reads one snapshot per observation window.
Every block keeps its reading explicit: a missing value is ``null`` and an
unavailable block says so, so a caller never mistakes a zero for "not
measured".
"""

from datetime import datetime

from pydantic import BaseModel, Field


class SourceMetrics(BaseModel):
    """Reader-side freshness and parsing state for the configured feeds."""

    available: bool = Field(description="False when the reader could not list the feeds")
    error: str | None = Field(
        default=None,
        description="Stable reason when the block is unavailable; null while the reader answers",
    )
    feeds: int = Field(default=0, description="Configured feeds the reader reported")
    disabled: int = Field(default=0, description="Feeds paused in the reader; freshness is only read for the others")
    checked_in_window: int = Field(default=0, description="Enabled feeds whose last check falls inside the window")
    stale: int = Field(
        default=0,
        description="Enabled feeds with no check or a check older than twice the configured polling interval",
    )
    parsing_errors: int = Field(default=0, description="Enabled feeds reporting at least one parsing error")
    newest_checked_at: datetime | None = Field(default=None, description="Newest last-check instant, in UTC")
    oldest_checked_at: datetime | None = Field(default=None, description="Oldest last-check instant, in UTC")


class IngestionMetrics(BaseModel):
    """Recorded ingestion passes that started inside the window."""

    runs: int = Field(default=0, description="Passes started in the window")
    successes: int = Field(default=0, description="Passes that closed as success")
    failures: int = Field(default=0, description="Passes that closed as failed")
    running: int = Field(default=0, description="Passes that had not closed when the snapshot was read")
    success_rate: float | None = Field(
        default=None,
        description="Successes over finished passes as a 0-1 fraction; null when no pass finished",
    )
    entries: int = Field(default=0, description="Entries recorded across the passes in the window")
    average_entries: float | None = Field(
        default=None,
        description="Entries per pass in the window; null when no pass was recorded",
    )
    last_run_id: int | None = Field(default=None, description="Newest recorded pass in the window")
    last_status: str | None = Field(default=None, description="Status of that pass")


class ReportMetrics(BaseModel):
    """Stored report editions created inside the window."""

    editions: int = Field(default=0, description="Editions created in the window, whatever their status")
    ready: int = Field(default=0, description="Editions with a generated text report")
    no_news: int = Field(default=0, description="Editions stored as no news for the requested period")
    failed: int = Field(default=0, description="Editions whose generation failed")
    average_included_entries: float | None = Field(
        default=None,
        description="Entries included per ready edition; null when no edition is ready",
    )
    p50_seconds: float | None = Field(
        default=None,
        description="Median wall time from edition creation to the newest story or update; null when unmeasurable",
    )
    p95_seconds: float | None = Field(
        default=None,
        description="95th percentile of that wall time; null when unmeasurable",
    )


class AudioMetrics(BaseModel):
    """Audio assets created inside the window."""

    assets: int = Field(default=0, description="Audio assets stored in the window")
    duration_seconds: float = Field(default=0.0, description="Sum of their durations")
    size_bytes: int = Field(default=0, description="Sum of their file sizes")
    editions_with_audio: int = Field(default=0, description="Distinct editions those assets belong to")


class MetricsSnapshot(BaseModel):
    """One reading of the pilot metrics for a window ending now."""

    days: int = Field(description="Window size in days")
    generated_at: datetime = Field(description="Instant the snapshot was built, in UTC")
    window_start: datetime = Field(description="Oldest instant included, in UTC")
    sources: SourceMetrics
    ingestion: IngestionMetrics
    reports: ReportMetrics
    audio: AudioMetrics
