"""Request and response shapes for on-demand reports.

The stored rows are projected through this module so the API owns its contract:
the columns can change without leaking straight to a caller. A summary carries
the provenance every edition keeps, and a detail adds the stories with their
claims and citations.
"""

from datetime import UTC, datetime
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.digest import Citation

ReportStatus = Literal["draft", "ready", "no_news", "failed"]
"""The states a stored report can be in."""


class ReportCreateRequest(BaseModel):
    """Selection a caller asks one report for.

    ``since_last`` resolves the period from the newest saved cursor and ignores
    the explicit period. Otherwise a period is used as given, and a request that
    names no period falls back to the configured default window.
    """

    period_start: datetime | None = Field(default=None, description="Start of the selection period, read as UTC")
    period_end: datetime | None = Field(default=None, description="End of the selection period, read as UTC")
    since_last: bool = Field(default=False, description="Select only entries published after the newest cursor")
    feed_ids: list[int] = Field(default_factory=list, description="Feeds to read; empty selects every feed")
    category_ids: list[int] = Field(default_factory=list, description="Categories to read when no feed is named")
    tags: list[str] | None = Field(default=None, description="Tags the reader requires all of")
    search: str | None = Field(default=None, description="Reader full-text query")
    read: bool | None = Field(default=None, description="Keep only read or unread entries")
    starred: bool | None = Field(default=None, description="Keep only starred or unstarred entries")
    max_entries: int | None = Field(default=None, ge=1, description="Requested selection size, capped by configuration")

    @model_validator(mode="after")
    def _check_period(self) -> Self:
        """Reject half a period and a range that runs backwards."""
        if (self.period_start is None) != (self.period_end is None):
            raise ValueError("period_start and period_end must be given together")
        if (
            self.period_start is not None
            and self.period_end is not None
            and _utc(self.period_start) > _utc(self.period_end)
        ):
            raise ValueError("period_start must not be after period_end")
        return self


class ReportStory(BaseModel):
    """One story with the claims it makes and the sources that support them."""

    model_config = ConfigDict(from_attributes=True)

    title: str = Field(description="Story headline")
    summary: str | None = Field(default=None, description="Spanish explanation of the story")
    claims: list[str] = Field(default_factory=list, description="Factual statements the story makes")
    citations: list[Citation] = Field(default_factory=list, description="Sources backing the claims")
    pub_type: str | None = Field(default=None, description="Announcement, release, research, news, or opinion")
    entities: list[dict[str, Any]] = Field(default_factory=list, description="Entities the story mentions")
    order_index: int = Field(default=0, description="Position of the story inside the report")

    @field_validator("claims", "citations", "entities", mode="before")
    @classmethod
    def _empty_list(cls, value: Any) -> Any:
        """Read a column left empty as an empty list."""
        return value or []

    @field_validator("order_index", mode="before")
    @classmethod
    def _position(cls, value: Any) -> int:
        """Read a missing position as the first one."""
        return 0 if value is None else value


class AudioAssetView(BaseModel):
    """One stored audio asset, as the report projection lists it."""

    model_config = ConfigDict(from_attributes=True)

    asset_id: int = Field(validation_alias="id", description="Identifier the asset is stored under")
    filename: str = Field(description="Dedicated WAV file name")
    duration_seconds: float | None = Field(default=None, description="Playback duration of the file")
    size_bytes: int | None = Field(default=None, description="Size of the stored file")
    provider: str | None = Field(default=None, description="Speech engine that produced the audio")
    voice: str | None = Field(default=None, description="Voice identifier used for synthesis")
    created_at: datetime | None = Field(default=None, description="When the asset was stored, in UTC")

    @field_validator("created_at", mode="before")
    @classmethod
    def _instant(cls, value: Any) -> Any:
        """Serve the stored instant as UTC-aware ISO-8601."""
        return _utc(value) if isinstance(value, datetime) else value


class ReportSummary(BaseModel):
    """One stored edition without its stories, as the history lists it."""

    model_config = ConfigDict(from_attributes=True)

    report_id: int = Field(validation_alias="id", description="Identifier the edition is stored under")
    status: ReportStatus = Field(description="draft, ready, no_news, or failed")
    title: str = Field(description="Title of the edition; Sin novedades when nothing was published")
    summary: str | None = Field(default=None, description="Spanish summary of the period")
    period_start: datetime | None = Field(default=None, description="Start of the period, in UTC")
    period_end: datetime | None = Field(default=None, description="End of the period, in UTC")
    filters: dict[str, Any] = Field(default_factory=dict, description="Selection filters the edition recorded")
    cursor: str | None = Field(default=None, description="Publication instant the edition reached")
    version: str | None = Field(default=None, description="Report schema version")
    entry_ids: list[int] = Field(default_factory=list, description="Reader entries included in the edition")
    meta: dict[str, Any] = Field(default_factory=dict, description="Generator metadata: model, prompt version, count")
    has_audio: bool = Field(default=False, description="Whether the edition has an audio asset")
    created_at: datetime | None = Field(default=None, description="When the edition was stored, in UTC")

    @field_validator("status", mode="before")
    @classmethod
    def _known_status(cls, value: Any) -> Any:
        """Read a row stored without a state as a draft."""
        return value or "draft"

    @field_validator("filters", "meta", mode="before")
    @classmethod
    def _empty_object(cls, value: Any) -> Any:
        """Read a column left empty as an empty object."""
        return value or {}

    @field_validator("entry_ids", mode="before")
    @classmethod
    def _identifiers(cls, value: Any) -> Any:
        """Read a column left empty as an empty selection."""
        return value or []

    @field_validator("has_audio", mode="before")
    @classmethod
    def _flag(cls, value: Any) -> bool:
        """Read a missing flag as false."""
        return bool(value)

    @field_validator("period_start", "period_end", "created_at", mode="before")
    @classmethod
    def _instant(cls, value: Any) -> Any:
        """Serve every stored instant as UTC-aware ISO-8601."""
        return _utc(value) if isinstance(value, datetime) else value


class ReportDetail(ReportSummary):
    """One stored edition with its stories, claims, citations, and audio assets."""

    stories: list[ReportStory] = Field(default_factory=list, description="Stories of the edition, in order")
    audio: list[AudioAssetView] = Field(
        default_factory=list,
        validation_alias="audio_assets",
        description="Audio assets stored for the edition",
    )

    @field_validator("audio", mode="before")
    @classmethod
    def _assets(cls, value: Any) -> Any:
        """Read a relationship left empty as an empty list."""
        return value or []


class ReportPagination(BaseModel):
    """Pagination metadata for one page of the report history."""

    page: int
    per_page: int
    total: int
    total_pages: int


class ReportListResponse(BaseModel):
    """One page of the report history, newest first."""

    data: list[ReportSummary]
    pagination: ReportPagination


class ReportResponse(BaseModel):
    """One edition wrapped in the single-resource envelope the API uses."""

    data: ReportSummary


class ReportDetailResponse(BaseModel):
    """One edition with its stories wrapped in the single-resource envelope."""

    data: ReportDetail


class AudioAssetResponse(BaseModel):
    """One audio asset wrapped in the single-resource envelope."""

    data: AudioAssetView


def _utc(value: datetime) -> datetime:
    """Return the instant in UTC, reading a naive value as already UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
