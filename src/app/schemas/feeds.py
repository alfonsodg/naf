"""Request schemas for feed management."""

from pydantic import BaseModel, Field, field_validator

from app.core.feed_urls import FeedURLError, validate_feed_url


class FeedCreateRequest(BaseModel):
    """Add one feed, optionally into a category created on demand."""

    feed_url: str = Field(description="Absolute http(s) URL of the feed document")
    category: str | None = Field(
        default=None,
        max_length=120,
        description="Category title; created when it does not exist yet",
    )

    @field_validator("feed_url")
    @classmethod
    def _check_url(cls, value: str) -> str:
        """Reject malformed or forbidden targets before any work is done."""
        try:
            return validate_feed_url(value)
        except FeedURLError as exc:
            raise ValueError(str(exc)) from exc

    @field_validator("category")
    @classmethod
    def _check_category(cls, value: str | None) -> str | None:
        """Reject a blank category title."""
        if value is None:
            return None
        trimmed = value.strip()
        return trimmed or None


class FeedUpdateRequest(BaseModel):
    """Change one feed. Omitted fields are left untouched."""

    title: str | None = Field(default=None, min_length=1, max_length=200)
    category_id: int | None = Field(default=None, ge=1)
    disabled: bool | None = Field(default=None, description="True pauses the feed")
