"""Response projection for the recorded ingestion runs.

The rows live in NAF-owned storage in the shape the recorder writes. The API
exposes a shape this project defines, so the fields can be documented and a
change in the table never leaks straight to a caller.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

IngestionRunStatus = Literal["running", "success", "failed"]
"""The states a recorded pass can be in."""


class IngestionRunError(BaseModel):
    """One feed failure recorded inside a pass."""

    feed_id: int | None = Field(default=None, description="Reader feed identifier, absent when unknown")
    error: str = Field(default="", description="Failure reported for that feed")


class IngestionRunResponse(BaseModel):
    """One recorded ingestion pass in the shape the API exposes."""

    run_id: int = Field(description="Identifier the pass is recorded under")
    adapter_name: str | None = Field(default=None, description="Reader the pass read from")
    status: str = Field(description="running, success, or failed")
    started_at: datetime | None = Field(default=None, description="When the pass started, in UTC")
    finished_at: datetime | None = Field(default=None, description="When the pass closed; absent while running")
    entries_count: int = Field(default=0, description="Entries the pass saw")
    errors: list[IngestionRunError] = Field(default_factory=list, description="Per-feed failures")
    error_summary: str | None = Field(default=None, description="Readable summary of the failures")


class IngestionRunPagination(BaseModel):
    """Pagination metadata for one page of the run history."""

    page: int
    per_page: int
    total: int
    total_pages: int


class IngestionRunListResponse(BaseModel):
    """One page of the run history with its pagination metadata."""

    data: list[IngestionRunResponse]
    pagination: IngestionRunPagination


class IngestionRunDetailResponse(BaseModel):
    """One run wrapped in the single-resource envelope the API uses."""

    data: IngestionRunResponse
