"""Digest and citation schemas."""

from typing import Any

from pydantic import BaseModel, Field


class Citation(BaseModel):
    """Reference tying a claim back to exactly one source entry."""

    entry_id: str
    entry_url: str
    title: str
    author: str | None = None
    quote: str | None = None
    relevance: float = 1.0


class DigestStory(BaseModel):
    """A story built from one or more cited entries."""

    title: str
    summary: str
    claims: list[str]
    citations: list[Citation]
    pub_type: str | None = None
    entities: list[dict[str, Any]] = Field(default_factory=list)


class Digest(BaseModel):
    """A generated report with an explicit period and filter set."""

    title: str
    summary: str
    period_start: str
    period_end: str
    filters: dict[str, Any] = Field(default_factory=dict)
    cursor: str | None = None
    stories: list[DigestStory]
    version: str = "1.0"
