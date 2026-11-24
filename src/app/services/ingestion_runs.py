"""Record the ingestion runs in NAF-owned storage.

A feed that starts failing must leave a trace. The reader exposes the current
parsing error count, but not which feed failed, when, or with what error, and
without that history neither the recovery state nor the pilot metric of
successful source runs can be measured.

Every pass is recorded here and read back here: one run by identifier and one
page of the history, newest first. The store owns the row-to-shape mapping so
the routes only validate and serialize it.
"""

from datetime import UTC, datetime
from typing import Any, Protocol, cast

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models import IngestionRun


class RunRecorder(Protocol):
    """Record one ingestion pass."""

    def start(self, adapter_name: str) -> int:
        """Open a run and return its identifier."""

    def finish(self, run_id: int, status: str, entries_count: int, errors: list[dict[str, Any]]) -> None:
        """Close a run with its result."""


class IngestionRunStore:
    """Store and read the ingestion runs."""

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

    def get_run(self, run_id: int) -> dict[str, Any] | None:
        """Return one recorded run, or None when the identifier is unknown."""
        row = self.session.get(IngestionRun, run_id)
        return None if row is None else _project(row)

    def list_runs(self, limit: int, offset: int = 0, status: str | None = None) -> tuple[list[dict[str, Any]], int]:
        """Return one page of the recorded runs, newest first, and the total count.

        ``status`` keeps only the runs in that state. The tie-breaker on the
        identifier keeps passes started in the same instant in a stable order.
        """
        statement = select(IngestionRun)
        counter = select(func.count()).select_from(IngestionRun)
        if status is not None:
            statement = statement.where(IngestionRun.status == status)
            counter = counter.where(IngestionRun.status == status)

        rows = self.session.execute(
            statement.order_by(IngestionRun.started_at.desc(), IngestionRun.id.desc()).limit(limit).offset(offset)
        ).scalars()
        total = self.session.execute(counter).scalar_one()
        return [_project(row) for row in rows], int(total)


def _project(row: IngestionRun) -> dict[str, Any]:
    """Map a run row to the shape the API exposes."""
    # The model declares its columns without Mapped annotations, so mypy reads
    # an instance attribute as the descriptor; the runtime value is the column.
    recorded: list[Any] = row.errors if isinstance(row.errors, list) else []
    return {
        "run_id": row.id,
        "adapter_name": row.adapter_name,
        "status": row.status or "running",
        "started_at": _utc(cast(datetime | None, row.started_at)),
        "finished_at": _utc(cast(datetime | None, row.finished_at)),
        "entries_count": row.entries_count or 0,
        "errors": [_project_error(error) for error in recorded if isinstance(error, dict)],
        "error_summary": row.error_summary,
    }


def _project_error(error: dict[str, Any]) -> dict[str, Any]:
    """Map one recorded feed failure to the shape the API exposes."""
    return {"feed_id": error.get("feed_id"), "error": error.get("error") or ""}


def _utc(value: datetime | None) -> datetime | None:
    """Return the instant in UTC, reading a naive value as already UTC."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _now() -> datetime:
    """Return the current UTC time in the naive form the columns use."""
    return datetime.now(UTC).replace(tzinfo=None)


def _summary(errors: list[dict[str, Any]]) -> str:
    """Summarize the per-feed errors of a run."""
    return "; ".join(f"feed {error.get('feed_id')}: {error.get('error')}" for error in errors)
