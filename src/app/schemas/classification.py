"""Classification result schema."""

from typing import Any

from pydantic import BaseModel, Field


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
    ai_enrichment: dict[str, Any] | None = None
    rationale: str = ""
