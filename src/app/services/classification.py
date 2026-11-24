"""Classify one reader entry on demand and keep the user's correction.

The reader keeps owning the entry and NAF owns the analysis. A failed
classification changes nothing, a repeated pass replaces the automatic answer
and its mentions, and a row the user corrected is returned untouched instead of
being overwritten.
"""

import json
from typing import Any, NamedTuple, cast

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.ports.classifier import Classifier
from app.core.ports.feed_reader import FeedReader
from app.models import EntryClassification, EntryModelMention
from app.schemas.classification import Classification, ClassificationCorrection, ModelMention
from app.services.collector import normalize_entry

PRESERVED_NOTICE = "La corrección del usuario se conserva; no se volvió a clasificar la entrada."
AUTO_VALUES_HEADER = "Valores automáticos originales:"
CORRECTABLE_FIELDS = ("category", "categories", "tags", "pub_type")


class ClassificationOutcome(NamedTuple):
    """Stored classification, its mentions, and whether a user correction won."""

    classification: EntryClassification
    models: list[EntryModelMention]
    preserved: bool = False


class ClassificationService:
    """Read one entry, classify it, and store or correct the result."""

    def __init__(self, session: Session, reader: FeedReader, classifier: Classifier) -> None:
        """Bind the service to storage, the reader port, and the classifier port."""
        self.session = session
        self.reader = reader
        self.classifier = classifier

    async def classify(self, entry_id: int) -> ClassificationOutcome:
        """Classify one entry and persist the answer with its model mentions.

        A row the user corrected is returned unchanged and flagged as preserved:
        an automatic pass never overwrites a correction. The entry is read only
        when the classification still belongs to the classifier, so a corrected
        entry stays readable while the reader is unavailable.
        """
        stored = self._stored(entry_id)
        if stored is not None and stored.source == "user":
            return ClassificationOutcome(stored, self._mentions(entry_id), preserved=True)

        raw = await self.reader.get_entry(entry_id)
        result = await self.classifier.classify(normalize_entry(raw))
        row = stored if stored is not None else EntryClassification(entry_id=entry_id)
        _apply(row, result)
        # The models declare columns without Mapped annotations, so mypy reads the
        # instance attributes as descriptors; the runtime values are plain values.
        row.source = "auto"  # type: ignore[assignment]
        row.model = self.classifier.model  # type: ignore[assignment]
        self.session.add(row)
        self._replace_mentions(entry_id, result.models)
        self.session.commit()
        self.session.refresh(row)
        return ClassificationOutcome(row, self._mentions(entry_id))

    def correct(self, entry_id: int, payload: ClassificationCorrection) -> ClassificationOutcome | None:
        """Apply a user correction and mark the row as owned by the user.

        Only the fields the request names change. When the automatic values
        change for the first time, they are appended to ``rationale`` so the
        original suggestion is not lost. Returns None when nothing is stored.
        """
        row = self._stored(entry_id)
        if row is None:
            return None
        updates = {name: getattr(payload, name) for name in payload.model_fields_set}
        changed = {name: value for name, value in updates.items() if getattr(row, name) != value}
        if changed and row.source == "auto":
            row.rationale = _with_auto_values(cast(str | None, row.rationale), row)  # type: ignore[assignment]
        for name, value in changed.items():
            setattr(row, name, value)
        row.source = "user"  # type: ignore[assignment]
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return ClassificationOutcome(row, self._mentions(entry_id))

    def get(self, entry_id: int) -> ClassificationOutcome | None:
        """Return the stored classification with its mentions, or None."""
        row = self._stored(entry_id)
        if row is None:
            return None
        return ClassificationOutcome(row, self._mentions(entry_id))

    def list_review(
        self, review_needed: bool | None, page: int, per_page: int
    ) -> tuple[list[EntryClassification], int]:
        """Return one page of stored classifications, newest first, and the total.

        ``review_needed`` filters the queue; omitting it lists every row.
        """
        filters = [] if review_needed is None else [EntryClassification.review_needed.is_(review_needed)]
        offset = (page - 1) * per_page
        statement = (
            select(EntryClassification)
            .where(*filters)
            .order_by(EntryClassification.created_at.desc(), EntryClassification.id.desc())
            .limit(per_page)
            .offset(offset)
        )
        rows = self.session.execute(statement).scalars().all()
        total = self.session.execute(select(func.count()).select_from(EntryClassification).where(*filters)).scalar_one()
        return list(rows), int(total)

    def _stored(self, entry_id: int) -> EntryClassification | None:
        """Return the classification stored for one entry, or None."""
        statement = select(EntryClassification).where(EntryClassification.entry_id == entry_id)
        return self.session.execute(statement).scalar_one_or_none()

    def _mentions(self, entry_id: int) -> list[EntryModelMention]:
        """Return the stored model mentions of one entry in insertion order."""
        statement = (
            select(EntryModelMention).where(EntryModelMention.entry_id == entry_id).order_by(EntryModelMention.id)
        )
        return list(self.session.execute(statement).scalars().all())

    def _replace_mentions(self, entry_id: int, mentions: list[ModelMention]) -> None:
        """Replace every mention of one entry with the new answer."""
        self.session.execute(delete(EntryModelMention).where(EntryModelMention.entry_id == entry_id))
        self.session.add_all([_mention_row(entry_id, mention) for mention in mentions])


def _apply(row: EntryClassification, result: Classification) -> None:
    """Copy the classifier answer onto the stored row.

    The models declare columns without Mapped annotations, so mypy reads each
    instance attribute as its descriptor; the runtime values are plain values.
    """
    row.category = result.category  # type: ignore[assignment]
    row.categories = result.categories  # type: ignore[assignment]
    row.tags = result.tags  # type: ignore[assignment]
    row.pub_type = result.pub_type  # type: ignore[assignment]
    row.is_official = result.is_official  # type: ignore[assignment]
    row.confidence = result.confidence  # type: ignore[assignment]
    row.uncertainty = result.uncertainty  # type: ignore[assignment]
    row.review_needed = result.review_needed  # type: ignore[assignment]
    row.rationale = result.rationale  # type: ignore[assignment]


def _mention_row(entry_id: int, mention: ModelMention) -> EntryModelMention:
    """Build one stored mention from the classifier answer."""
    return EntryModelMention(
        entry_id=entry_id,
        name=mention.name,
        creator=mention.creator,
        change_type=mention.change_type,
        official=mention.official,
        evidence_quote=mention.evidence_quote,
        evidence_url=mention.evidence_url,
        confidence=mention.confidence,
    )


def _with_auto_values(rationale: str | None, row: EntryClassification) -> str:
    """Append the automatic values a correction replaced to the rationale."""
    snapshot: dict[str, Any] = {name: getattr(row, name) for name in CORRECTABLE_FIELDS}
    line = f"{AUTO_VALUES_HEADER} {json.dumps(snapshot, ensure_ascii=False, default=str)}"
    current = (rationale or "").strip()
    return f"{current}\n{line}" if current else line
