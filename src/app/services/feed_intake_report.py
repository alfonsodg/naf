"""The intake report: one row per input URL and how it is serialized.

The row is the contract the caller reads: whether the candidate was processed,
what verdict it got, which category was applied, which folders were only seen
in the source document, and why it was refused. Keeping it apart from the
decision logic is what lets the service stay about deciding.
"""

from dataclasses import dataclass, field
from typing import Any

from app.core.ports.feed_validator import FeedVerdict
from app.services.feed_documents import CandidateFeed


@dataclass(slots=True)
class IntakeRow:
    """One row of the intake report, one per input URL."""

    url: str
    verdict: str
    status_code: int | None = None
    item_count: int = 0
    added: bool = False
    disabled: bool = False
    duplicate: bool = False
    processed: bool = True
    applied_category: str = ""
    reported_categories: list[str] = field(default_factory=list)
    reason: str = ""


def count_verdicts(rows: list[IntakeRow]) -> dict[str, int]:
    """Count rows per verdict for the summary block."""
    counts: dict[str, int] = {}
    for row in rows:
        counts[row.verdict] = counts.get(row.verdict, 0) + 1
    return counts


def chunks(candidates: list[CandidateFeed], size: int) -> list[list[CandidateFeed]]:
    """Split the candidates into batches small enough to keep the budget."""
    return [candidates[index : index + size] for index in range(0, len(candidates), size)]


def not_processed_rows(candidates: list[CandidateFeed]) -> list[IntakeRow]:
    """Report the candidates the batch limit or the time budget left out.

    They are reported, never dropped, so the user knows the payload was only
    partly handled and can send it again to continue.
    """
    return [
        IntakeRow(
            url=candidate.url,
            verdict=str(FeedVerdict.NOT_PROCESSED),
            processed=False,
            reason="the intake budget was reached; send the remaining URLs again to continue",
        )
        for candidate in candidates
    ]


def row_payload(row: IntakeRow) -> dict[str, Any]:
    """Serialize one intake row for the HTTP response."""
    return {
        "url": row.url,
        "verdict": row.verdict,
        "status_code": row.status_code,
        "item_count": row.item_count,
        "added": row.added,
        "disabled": row.disabled,
        "duplicate": row.duplicate,
        "processed": row.processed,
        "applied_category": row.applied_category,
        "reported_categories": row.reported_categories,
        "reason": row.reason,
    }
