"""Record the ingestion runs in NAF-owned storage.

A feed that starts failing must leave a trace. The reader exposes the current
parsing error count, but not which feed failed, when, or with what error, and
without that history neither the recovery state nor the pilot metric of
successful source runs can be measured.
"""

from datetime import UTC, datetime
from typing import Any, Protocol

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models import IngestionRun


class RunRecorder(Protocol):
    """Record one ingestion pass."""

    def start(self, adapter_name: str) -> int:
        """Open a run and return its identifier."""

    def finish(self, run_id: int, status: str, entries_count: int, errors: list[dict[str, Any]]) -> None:
        """Close a run with its result."""


class IngestionRunStore:
    """Store the ingestion runs."""

    def __init__(self, session: Session) -> None:
        """Bind the store to a database session."""
        self.session = session

    def start(self, adapter_name: str) -> int:
        """Open a run and return its identifier."""
        run = IngestionRun(adapter_name=adapter_name, started_at=_now(), status="running")
        self.session.add(run)
        self.session.commit()
        return int(run.id)

    def finish(self, run_id: int, status: str, entries_count: int, errors: list[dict[str, Any]]) -> None:
        """Close a run with its result."""
        self.session.execute(
            update(IngestionRun)
            .where(IngestionRun.id == run_id)
            .values(
                finished_at=_now(),
                status=status,
                entries_count=entries_count,
                errors=errors,
                error_summary=_summary(errors),
            )
        )
        self.session.commit()


def _now() -> datetime:
    """Return the current UTC time in the naive form the columns use."""
    return datetime.now(UTC).replace(tzinfo=None)


def _summary(errors: list[dict[str, Any]]) -> str:
    """Summarize the per-feed errors of a run."""
    return "; ".join(f"feed {error.get('feed_id')}: {error.get('error')}" for error in errors)
