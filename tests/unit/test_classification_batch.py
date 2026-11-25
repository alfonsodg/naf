"""The bounded backlog pass: only unclassified entries, a hard limit, partial failure.

A fake reader serves a newest-first page and a fake classifier records the
entries it is asked about, so the pass is exercised without a network call.
"""

from collections.abc import Callable, Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from tests.classification_support import FakeClassifier, FakeReader, entry, settings_with

from app.db.base import Base
from app.db.session import get_session
from app.main import app
from app.models import EntryClassification
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


def _store(session: Session, entry_id: int, source: str = "auto", category: str = "Tecnología y software") -> None:
    """Seed one stored classification owned by the classifier or the user."""
    session.add(
        EntryClassification(
            entry_id=entry_id,
            category=category,
            categories=[],
            tags=[],
            pub_type="news",
            is_official=False,
            confidence=0.5,
            uncertainty=False,
            review_needed=False,
            rationale="",
            source=source,
            model="classifier-model",
        )
    )
    session.commit()


def _row(session: Session, entry_id: int) -> EntryClassification:
    """Return the only classification stored for one entry."""
    statement = select(EntryClassification).where(EntryClassification.entry_id == entry_id)
    return session.execute(statement).scalars().one()


def test_batch_classifies_only_the_unclassified_entries_in_order(session: Session, wire: Callable[..., Any]) -> None:
    """Stored automatic rows and user corrections are skipped, newest first."""
    reader, classifier = wire(reader=FakeReader(entries=[entry(4), entry(3), entry(2), entry(1)]))
    _store(session, 3)
    _store(session, 2, source="user", category="Ciencia y espacio")

    response = client.post("/api/v1/classifications/run", json={"limit": 5})

    assert response.status_code == 200
    body = response.json()
    assert body["classified"] == 2
    assert body["entry_ids"] == [4, 1]
    assert [row["entry_id"] for row in body["data"]] == [4, 1]
    assert body["scanned"] == 4
    assert body["stopped_reason"] is None
    assert [call["entry_id"] for call in classifier.calls] == [4, 1]
    assert reader.calls == [4, 1]
    assert reader.list_calls == [100]
    assert _row(session, 2).source == "user"
    assert _row(session, 2).category == "Ciencia y espacio"
    assert _row(session, 3).source == "auto"


def test_batch_respects_the_limit(session: Session, wire: Callable[..., Any]) -> None:
    """The pass never classifies more entries than the request allows."""
    wire(reader=FakeReader(entries=[entry(identifier) for identifier in range(5, 0, -1)]))

    response = client.post("/api/v1/classifications/run", json={"limit": 2})

    assert response.status_code == 200
    body = response.json()
    assert body["classified"] == 2
    assert body["entry_ids"] == [5, 4]
    stored = session.execute(select(EntryClassification.entry_id).order_by(EntryClassification.entry_id)).scalars()
    assert list(stored) == [4, 5]


def test_batch_stops_on_the_first_provider_failure_and_reports_it(session: Session, wire: Callable[..., Any]) -> None:
    """The committed entries survive, the failure is explained, and nothing later runs."""
    reader, classifier = wire(reader=FakeReader(entries=[entry(identifier) for identifier in range(5, 0, -1)]))
    classifier.fail_on = {3}

    response = client.post("/api/v1/classifications/run", json={"limit": 4})

    assert response.status_code == 200
    body = response.json()
    assert body["classified"] == 2
    assert body["entry_ids"] == [5, 4]
    assert "proveedor" in body["stopped_reason"]
    assert [call["entry_id"] for call in classifier.calls] == [5, 4, 3]
    assert reader.calls == [5, 4, 3]
    stored = session.execute(select(EntryClassification.entry_id).order_by(EntryClassification.entry_id)).scalars()
    assert list(stored) == [4, 5]


def test_a_failure_on_the_first_entry_completes_nothing(session: Session, wire: Callable[..., Any]) -> None:
    """A provider that fails immediately leaves the backlog untouched."""
    _, classifier = wire(reader=FakeReader(entries=[entry(2), entry(1)]))
    classifier.fail_on = {2}

    response = client.post("/api/v1/classifications/run", json={"limit": 2})

    body = response.json()
    assert body["classified"] == 0
    assert body["entry_ids"] == []
    assert body["stopped_reason"]
    assert session.execute(select(EntryClassification)).first() is None


def test_batch_without_a_configured_model_is_a_503(session: Session, wire: Callable[..., Any]) -> None:
    """No model means no reader call and no stored row."""
    reader, classifier = wire(llm_model="")

    response = client.post("/api/v1/classifications/run", json={"limit": 2})

    assert response.status_code == 503
    assert response.json()["detail"]["error"]["code"] == "CLASSIFIER_NOT_CONFIGURED"
    assert reader.list_calls == []
    assert classifier.calls == []


def test_the_batch_limits_are_validated(session: Session, wire: Callable[..., Any]) -> None:
    """The request, the query, and the pass share the documented bounds."""
    wire()

    assert client.post("/api/v1/classifications/run", json={"limit": 0}).status_code == 422
    assert client.post("/api/v1/classifications/run", json={"limit": 21}).status_code == 422
    assert client.post("/api/v1/classifications/run", json={}).status_code == 422
    assert client.get("/api/v1/classifications/pending", params={"limit": 0}).status_code == 422
    assert client.get("/api/v1/classifications/pending", params={"limit": 51}).status_code == 422


def test_pending_counts_the_recent_entries_without_a_classification(session: Session, wire: Callable[..., Any]) -> None:
    """Every stored row counts as classified, including a user correction."""
    wire(reader=FakeReader(entries=[entry(identifier) for identifier in range(5, 0, -1)]))
    _store(session, 5)
    _store(session, 3)
    _store(session, 1, source="user", category="Ciencia y espacio")

    response = client.get("/api/v1/classifications/pending", params={"limit": 5})

    assert response.status_code == 200
    assert response.json() == {"scanned": 5, "pending": 2}


def test_pending_scans_only_the_requested_window(session: Session, wire: Callable[..., Any]) -> None:
    """The backlog count is bounded by the limit, not by the reader history."""
    reader, _ = wire(reader=FakeReader(entries=[entry(identifier) for identifier in range(5, 0, -1)]))

    response = client.get("/api/v1/classifications/pending", params={"limit": 2})

    assert response.json() == {"scanned": 2, "pending": 2}
    assert reader.list_calls == [2]
