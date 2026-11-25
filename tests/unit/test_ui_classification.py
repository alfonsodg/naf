"""The sources page runs the bounded backlog pass and reports its result.

The reader and the classifier are replaced at the page boundary, so the route,
the service, the redirect, and the rendered notice are exercised together.
"""

from collections.abc import Callable, Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from tests.classification_support import FakeClassifier, FakeReader, entry
from tests.ui_fixtures import settings

from app.db.base import Base
from app.db.session import get_session
from app.main import app
from app.models import EntryClassification
from app.routers import ui

client = TestClient(app)


class BacklogReader(FakeReader):
    """Reader double that also serves the empty feed list the sources page reads."""

    def __init__(self, entries: list[dict[str, Any]]) -> None:
        """Bind the backlog by name; FakeReader's first positional flag is ``missing``."""
        super().__init__(entries=entries)

    async def list_feeds(self) -> list[dict[str, Any]]:
        """Return no feeds: these tests only exercise the classification action."""
        return []


@pytest.fixture
def session() -> Iterator[Session]:
    """Yield a session bound to a fresh in-memory database, served by the pages."""
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
def wire(monkeypatch: pytest.MonkeyPatch) -> Callable[..., FakeClassifier]:
    """Replace the reader, the classifier, and the settings the page builds."""

    def _wire(
        reader: FakeReader | None = None,
        classifier: FakeClassifier | None = None,
        **overrides: Any,
    ) -> FakeClassifier:
        active_classifier = classifier or FakeClassifier()
        monkeypatch.setattr(ui, "_reader", lambda: reader or BacklogReader([]))
        monkeypatch.setattr(ui, "_classifier", lambda: active_classifier)
        monkeypatch.setattr(ui, "app_settings", settings(**overrides))
        return active_classifier

    return _wire


def _store_user_correction(session: Session, entry_id: int) -> None:
    """Seed one row the user owns, which the pass must never overwrite."""
    session.add(
        EntryClassification(
            entry_id=entry_id,
            category="Ciencia y espacio",
            categories=[],
            tags=[],
            pub_type="news",
            is_official=False,
            confidence=0.5,
            uncertainty=False,
            review_needed=False,
            rationale="",
            source="user",
            model="classifier-model",
        )
    )
    session.commit()


def test_the_page_classifies_the_backlog_and_reports_the_count(
    session: Session, wire: Callable[..., FakeClassifier]
) -> None:
    """The action runs the service and redirects with the completed count."""
    classifier = wire(reader=BacklogReader([entry(2), entry(1)]))

    response = client.post("/ui/classify", data={"limit": "2"}, follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/sources?notice=classified&classified=2"
    page = client.get(response.headers["location"])
    assert page.status_code == 200
    assert "Se clasificaron 2 novedades." in page.text
    assert 'action="/ui/classify"' in page.text
    assert [call["entry_id"] for call in classifier.calls] == [2, 1]
    assert session.execute(select(EntryClassification)).scalars().all() != []


def test_the_page_never_overwrites_a_user_correction(session: Session, wire: Callable[..., FakeClassifier]) -> None:
    """A corrected entry is skipped and its values stay exactly as the user left them."""
    classifier = wire(reader=BacklogReader([entry(2), entry(1)]))
    _store_user_correction(session, 1)

    response = client.post("/ui/classify", data={"limit": "2"}, follow_redirects=False)

    assert response.headers["location"] == "/sources?notice=classified&classified=1"
    assert [call["entry_id"] for call in classifier.calls] == [2]
    row = session.execute(select(EntryClassification).where(EntryClassification.entry_id == 1)).scalars().one()
    assert row.source == "user"
    assert row.category == "Ciencia y espacio"


def test_a_provider_failure_reports_what_was_completed(session: Session, wire: Callable[..., FakeClassifier]) -> None:
    """The page explains the recoverable failure without leaking provider detail."""
    classifier = wire(reader=BacklogReader([entry(2), entry(1)]))
    classifier.fail_on = {1}

    response = client.post("/ui/classify", data={"limit": "2"}, follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/sources?error=classify&classified=1"
    page = client.get(response.headers["location"])
    assert page.status_code == 200
    assert "Se clasificaron 1 novedades antes del fallo." in page.text
    assert "No se pudo completar la clasificación" in page.text
    assert "Volver a intentarlo" in page.text
    assert "the provider refused" not in page.text


def test_an_unconfigured_model_is_explained(session: Session, wire: Callable[..., FakeClassifier]) -> None:
    """Without a model the page redirects to a readable message and runs nothing."""
    classifier = wire(reader=BacklogReader([entry(1)]), llm_model="")

    response = client.post("/ui/classify", data={"limit": "1"}, follow_redirects=False)

    assert response.headers["location"] == "/sources?error=classify-config"
    page = client.get(response.headers["location"])
    assert "La clasificación no está configurada" in page.text
    assert classifier.calls == []


def test_an_invalid_limit_is_explained(session: Session, wire: Callable[..., FakeClassifier]) -> None:
    """A limit outside the contract is refused with a recoverable message."""
    wire(reader=BacklogReader([entry(1)]))

    response = client.post("/ui/classify", data={"limit": "99"}, follow_redirects=False)

    assert response.headers["location"] == "/sources?error=classify-limit"
    page = client.get(response.headers["location"])
    assert "entre 1 y 20" in page.text
    assert session.execute(select(EntryClassification)).first() is None
