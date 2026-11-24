"""The classification API: persistence, corrections, evidence, and the review queue.

A fake reader stands in for Miniflux and a fake classifier for the LLM, so the
tests exercise routing, persistence, the correction rules, and the error
contract without a network call or a real model.
"""

from collections.abc import Callable, Iterator
from datetime import datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from tests.classification_support import FakeClassifier, FakeReader, settings_with

from app.core.exceptions import ClassificationError
from app.db.base import Base
from app.db.session import get_session
from app.main import app
from app.models import EntryClassification, EntryModelMention
from app.routers import classification

client = TestClient(app)


@pytest.fixture
def session() -> Iterator[Session]:
    """Yield a session bound to a fresh in-memory database, served by the API."""
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    opened = factory()
    app.dependency_overrides[get_session] = lambda: opened
    try:
        yield opened
    finally:
        app.dependency_overrides.clear()
        opened.close()
        engine.dispose()


@pytest.fixture
def wire(monkeypatch: pytest.MonkeyPatch) -> Callable[..., tuple[FakeReader, FakeClassifier]]:
    """Replace the reader, the classifier, and the settings the routes build."""

    def _wire(
        reader: FakeReader | None = None,
        classifier: FakeClassifier | None = None,
        **overrides: Any,
    ) -> tuple[FakeReader, FakeClassifier]:
        active_reader = reader or FakeReader()
        active_classifier = classifier or FakeClassifier()
        monkeypatch.setattr(classification, "_reader", lambda: active_reader)
        monkeypatch.setattr(classification, "_classifier", lambda: active_classifier)
        monkeypatch.setattr(classification, "app_settings", settings_with(**overrides))
        return active_reader, active_classifier

    return _wire


def _classify() -> Any:
    """Ask the API to classify the fake entry."""
    return client.post("/api/v1/entries/10/classify")


def _store(session: Session, entry_id: int, review_needed: bool, created_at: datetime) -> None:
    """Seed one stored classification with a deterministic creation instant."""
    session.add(
        EntryClassification(
            entry_id=entry_id,
            category="Tecnología y software",
            categories=[],
            tags=[],
            pub_type="news",
            is_official=False,
            confidence=0.5,
            uncertainty=False,
            review_needed=review_needed,
            rationale="",
            source="auto",
            model="classifier-model",
            created_at=created_at,
            updated_at=created_at,
        )
    )
    session.commit()


def test_classification_is_stored_with_its_mentions(session: Session, wire: Callable[..., Any]) -> None:
    """The route persists the answer, the model, and the evidence-backed mention."""
    reader, classifier = wire()

    response = _classify()

    assert response.status_code == 201
    body = response.json()
    assert body["data"]["entry_id"] == 10
    assert body["data"]["source"] == "auto"
    assert body["data"]["model"] == "classifier-model"
    assert body["data"]["category"] == "Tecnología y software"
    assert body["data"]["is_official"] is True
    assert body["models"][0]["name"] == "Modelo X"
    assert body["models"][0]["change_type"] == "new_model"
    assert body["models"][0]["official"] is True
    assert body["models"][0]["evidence_quote"] == "anuncia el lanzamiento de Modelo X"
    assert reader.calls == [10]
    assert classifier.calls[0]["entry_id"] == 10
    stored = session.execute(select(EntryClassification)).scalars().one()
    assert stored.entry_id == 10
    assert stored.source == "auto"
    mentions = session.execute(select(EntryModelMention)).scalars().all()
    assert [mention.name for mention in mentions] == ["Modelo X"]


def test_the_stored_classification_is_readable_without_a_configured_model(
    session: Session, wire: Callable[..., Any]
) -> None:
    """GET returns the row and its mentions even when the model is unconfigured."""
    wire()
    created = _classify().json()
    wire(llm_model="")

    response = client.get("/api/v1/entries/10/classification")

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["entry_id"] == 10
    assert body["models"][0]["mention_id"] == created["models"][0]["mention_id"]


def test_an_entry_that_was_never_classified_is_a_404(session: Session, wire: Callable[..., Any]) -> None:
    """A missing row answers the documented envelope, not an empty success."""
    wire()

    response = client.get("/api/v1/entries/99/classification")

    assert response.status_code == 404
    assert response.json()["detail"]["error"]["code"] == "CLASSIFICATION_NOT_FOUND"
    assert client.patch("/api/v1/entries/99/classification", json={"tags": ["modelos"]}).status_code == 404


def test_patch_marks_the_row_as_user_and_keeps_the_automatic_values(session: Session, wire: Callable[..., Any]) -> None:
    """A correction owns the four editable fields and preserves the suggestion."""
    wire()
    _classify()

    response = client.patch(
        "/api/v1/entries/10/classification",
        json={"category": "Ciencia y espacio", "tags": ["astronomía"]},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["source"] == "user"
    assert data["category"] == "Ciencia y espacio"
    assert data["tags"] == ["astronomía"]
    assert data["categories"] == ["Tecnología y software", "IA y modelos"]
    assert "Valores automáticos originales" in data["rationale"]
    assert "Tecnología y software" in data["rationale"]
    assert client.patch("/api/v1/entries/10/classification", json={}).status_code == 422
    assert client.patch("/api/v1/entries/10/classification", json={"category": None}).status_code == 422


def test_a_second_classification_does_not_overwrite_a_correction(session: Session, wire: Callable[..., Any]) -> None:
    """A corrected row is returned unchanged, and the reader and model are not called."""
    reader, classifier = wire()
    _classify()
    client.patch("/api/v1/entries/10/classification", json={"category": "Ciencia y espacio"})
    calls = len(classifier.calls)

    response = _classify()

    assert response.status_code == 201
    body = response.json()
    assert body["data"]["category"] == "Ciencia y espacio"
    assert body["data"]["source"] == "user"
    assert body["notice"]
    assert len(classifier.calls) == calls
    assert reader.calls == [10]


def test_an_unknown_entry_is_a_404_without_storing_anything(session: Session, wire: Callable[..., Any]) -> None:
    """The reader's 404 becomes ENTRY_NOT_FOUND and leaves no partial row."""
    reader, classifier = wire(reader=FakeReader(missing=True))

    response = _classify()

    assert response.status_code == 404
    assert response.json()["detail"]["error"]["code"] == "ENTRY_NOT_FOUND"
    assert reader.calls == [10]
    assert classifier.calls == []
    assert session.execute(select(EntryClassification)).first() is None


def test_an_unconfigured_model_is_refused_before_the_reader(session: Session, wire: Callable[..., Any]) -> None:
    """Without a model the route answers 503 and touches neither the reader nor the classifier."""
    reader, classifier = wire(llm_model="")

    response = _classify()

    assert response.status_code == 503
    assert response.json()["detail"]["error"]["code"] == "CLASSIFIER_NOT_CONFIGURED"
    assert reader.calls == []
    assert classifier.calls == []
    assert session.execute(select(EntryClassification)).first() is None


def test_invalid_classifier_output_is_a_502(session: Session, wire: Callable[..., Any]) -> None:
    """A classifier failure answers CLASSIFICATION_FAILED and stores no row."""
    _, classifier = wire()
    classifier.error = ClassificationError("the classifier did not return a valid answer")

    response = _classify()

    assert response.status_code == 502
    assert response.json()["detail"]["error"]["code"] == "CLASSIFICATION_FAILED"
    assert session.execute(select(EntryClassification)).first() is None


def test_the_review_queue_filters_and_paginates(session: Session, wire: Callable[..., Any]) -> None:
    """The queue returns newest first, honors the review filter, and reports its total."""
    wire()
    _store(session, 1, False, datetime(2026, 11, 21, 10))
    _store(session, 2, True, datetime(2026, 11, 22, 10))
    _store(session, 3, True, datetime(2026, 11, 23, 10))

    first = client.get(
        "/api/v1/classifications",
        params={"review_needed": "true", "page": 1, "per_page": 1},
    )
    assert first.status_code == 200
    body = first.json()
    assert [row["entry_id"] for row in body["data"]] == [3]
    assert body["pagination"] == {"page": 1, "per_page": 1, "total": 2, "total_pages": 2}

    second = client.get(
        "/api/v1/classifications",
        params={"review_needed": "true", "page": 2, "per_page": 1},
    )
    assert [row["entry_id"] for row in second.json()["data"]] == [2]

    settled = client.get("/api/v1/classifications", params={"review_needed": "false"})
    assert [row["entry_id"] for row in settled.json()["data"]] == [1]
    assert settled.json()["pagination"]["total"] == 1

    every_row = client.get("/api/v1/classifications")
    assert [row["entry_id"] for row in every_row.json()["data"]] == [3, 2, 1]
