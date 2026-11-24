"""Classification schemas: the classifier answer and the projections the API serves.

A classification is a suggestion, so every field can express doubt: a null
category, a low confidence, or an explicit review flag. The stored row carries
the automatic answer and the user correction side by side through ``source``
and ``rationale``.
"""

from datetime import UTC, datetime
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ChangeType = Literal["new_model", "model_update", "unknown"]
"""How an entry relates to a model: a new release, a revision, or unclear."""

ClassificationSource = Literal["auto", "user"]
"""Who owns the stored values: the classifier or the user."""


class ModelMention(BaseModel):
    """One model an entry names, with the evidence that supports the mention.

    ``official`` is null when the entry does not settle whether its own source
    is the creator's channel. ``evidence_quote`` is expected to be a literal
    fragment of the entry; an empty quote means the mention has no verbatim
    support and is therefore unverified.
    """

    name: str = Field(description="Model or family name as the entry writes it")
    creator: str | None = Field(default=None, description="Creator the entry attributes the model to")
    change_type: ChangeType = Field(default="unknown", description="New release, revision, or unclear")
    official: bool | None = Field(default=None, description="Whether the entry comes from the creator's channel")
    evidence_quote: str = Field(default="", description="Literal fragment of the entry supporting the mention")
    evidence_url: str = Field(default="", description="URL the evidence points to")
    confidence: float = Field(default=0.0, description="How sure the classifier is about this mention, 0 to 1")


class Classification(BaseModel):
    """Categorized view of one reader item.

    Uncertainty is explicit: an item the model cannot place stays unclassified
    and is flagged for review instead of being force-fitted into a category.
    """

    category: str | None = None
    categories: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    pub_type: str | None = None
    is_official: bool | None = None
    confidence: float = 0.0
    uncertainty: bool = False
    review_needed: bool = False
    rationale: str = ""
    models: list[ModelMention] = Field(default_factory=list)
    ai_enrichment: dict[str, Any] | None = None


class ClassificationView(BaseModel):
    """One stored classification, as the API serves it."""

    model_config = ConfigDict(from_attributes=True)

    entry_id: int = Field(description="Reader identifier of the classified entry")
    category: str | None = Field(default=None, description="Suggested main category")
    categories: list[str] = Field(default_factory=list, description="Every suggested category")
    tags: list[str] = Field(default_factory=list, description="Suggested tags")
    pub_type: str | None = Field(default=None, description="Suggested publication type")
    is_official: bool | None = Field(default=None, description="Whether the entry is the creator's own channel")
    confidence: float = Field(default=0.0, description="Confidence of the automatic answer, 0 to 1")
    uncertainty: bool = Field(default=False, description="The classifier could not place the entry with confidence")
    review_needed: bool = Field(default=False, description="The entry asks for human review")
    rationale: str = Field(default="", description="Why the classifier answered this, in Spanish")
    source: ClassificationSource = Field(default="auto", description="Whether the classifier or the user owns it")
    model: str = Field(default="", description="LLM that produced the automatic answer")
    created_at: datetime | None = Field(default=None, description="When the row was first stored, in UTC")
    updated_at: datetime | None = Field(default=None, description="When the row was last changed, in UTC")

    @field_validator("categories", "tags", mode="before")
    @classmethod
    def _list_value(cls, value: Any) -> Any:
        """Read a column left empty as an empty list."""
        return value or []

    @field_validator("rationale", "model", mode="before")
    @classmethod
    def _text_value(cls, value: Any) -> Any:
        """Read a column left empty as an empty string."""
        return "" if value is None else value

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def _instant(cls, value: Any) -> Any:
        """Serve the stored instant as UTC-aware ISO-8601."""
        return _utc(value) if isinstance(value, datetime) else value


class ModelMentionView(BaseModel):
    """One stored model mention, as the API serves it."""

    model_config = ConfigDict(from_attributes=True)

    mention_id: int = Field(validation_alias="id", description="Identifier the mention is stored under")
    entry_id: int = Field(description="Reader identifier of the entry that names the model")
    name: str = Field(description="Model or family name the entry uses")
    creator: str | None = Field(default=None, description="Creator attributed by the entry")
    change_type: ChangeType = Field(default="unknown", description="New model, model update, or unknown")
    official: bool | None = Field(default=None, description="Whether the entry is the creator's channel")
    evidence_quote: str = Field(default="", description="Literal fragment of the entry; empty means unverified")
    evidence_url: str = Field(default="", description="URL the evidence points to")
    confidence: float = Field(default=0.0, description="Confidence of the mention, 0 to 1")
    created_at: datetime | None = Field(default=None, description="When the mention was stored, in UTC")

    @field_validator("evidence_quote", "evidence_url", mode="before")
    @classmethod
    def _text_value(cls, value: Any) -> Any:
        """Read a column left empty as an empty string."""
        return "" if value is None else value

    @field_validator("created_at", mode="before")
    @classmethod
    def _instant(cls, value: Any) -> Any:
        """Serve the stored instant as UTC-aware ISO-8601."""
        return _utc(value) if isinstance(value, datetime) else value


class ClassificationCorrection(BaseModel):
    """Fields the user may correct; everything else stays owned by the classifier.

    An empty body is refused, and so is a body whose fields are all null: a
    correction must actually name a value. An explicit empty list clears the
    corresponding selection.
    """

    category: str | None = Field(default=None, description="Main category the user chooses")
    categories: list[str] | None = Field(default=None, description="Categories the user chooses")
    tags: list[str] | None = Field(default=None, description="Tags the user chooses")
    pub_type: str | None = Field(default=None, description="Publication type the user chooses")

    @model_validator(mode="after")
    def _at_least_one_value(self) -> Self:
        """Refuse a correction that changes nothing."""
        values = (self.category, self.categories, self.tags, self.pub_type)
        if all(value is None for value in values):
            raise ValueError("at least one of category, categories, tags, or pub_type is required")
        return self


class ClassificationResponse(BaseModel):
    """Automatic classification or correction with its model mentions."""

    data: ClassificationView
    models: list[ModelMentionView] = Field(default_factory=list)
    notice: str | None = Field(default=None, description="Spanish note when a user correction was preserved")


class ClassificationDetailResponse(BaseModel):
    """Stored classification with its model mentions."""

    data: ClassificationView
    models: list[ModelMentionView] = Field(default_factory=list)


class ClassificationPagination(BaseModel):
    """Pagination metadata of the review queue."""

    page: int
    per_page: int
    total: int
    total_pages: int


class ClassificationListResponse(BaseModel):
    """One page of stored classifications, newest first."""

    data: list[ClassificationView] = Field(default_factory=list)
    pagination: ClassificationPagination


def _utc(value: datetime) -> datetime:
    """Read a stored naive instant as UTC and normalise an aware one."""
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
