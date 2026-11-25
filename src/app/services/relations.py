"""Persist the related coverage a stored report already grouped.

The report groups several entries under one story; this service keeps that
grouping as data, so a later reader can find the sibling coverage and every
original entry stays readable.
"""

from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import Digest, EntryRelation


def persist_report_relations(session: Session, digest: Digest) -> int:
    """Store one symmetric relation per pair of entries cited by the same story."""
    pairs: set[tuple[int, int]] = set()
    for story in digest.stories:
        identifiers = sorted(
            {
                int(str(citation.get("entry_id")))
                for citation in (story.citations or [])
                if str(citation.get("entry_id", "")).isdigit()
            }
        )
        for position, left in enumerate(identifiers):
            for right in identifiers[position + 1 :]:
                pairs.add((left, right))

    created = 0
    for left, right in sorted(pairs):
        exists = session.execute(
            select(EntryRelation.id).where(
                EntryRelation.entry_id == left,
                EntryRelation.related_entry_id == right,
                EntryRelation.report_id == digest.id,
            )
        ).scalar_one_or_none()
        if exists is None:
            session.add(EntryRelation(entry_id=left, related_entry_id=right, report_id=digest.id))
            created += 1
    session.commit()
    return created


def related_entries(session: Session, entry_id: int) -> list[dict[str, Any]]:
    """Return the entries a stored report grouped with this one."""
    statement = select(EntryRelation).where(
        or_(EntryRelation.entry_id == entry_id, EntryRelation.related_entry_id == entry_id)
    )
    rows = session.execute(statement).scalars().all()
    return [
        {
            "entry_id": row.related_entry_id if row.entry_id == entry_id else row.entry_id,
            "kind": row.kind,
            "report_id": row.report_id,
        }
        for row in rows
    ]
