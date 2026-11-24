"""The server-rendered pages: creation, reading, the synced player, and sources.

A fake reader, generator, speech engine, and storage stand in for the external
parts, so the pages are exercised with the real services and a SQLite session.
"""

from collections.abc import Callable, Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from tests.ui_fixtures import (
    SEGMENTS,
    FakeGenerator,
    FakeReader,
    FakeStorage,
    FakeTTS,
    entry,
    make_report,
    report_form,
    settings,
)

from app.core.exceptions import MinifluxAPIError, ReportGenerationError, TTSError
from app.db.base import Base
from app.db.session import get_session
from app.main import app
from app.models import AudioAsset, Digest
from app.routers import ui

client = TestClient(app)


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
def wire(monkeypatch: pytest.MonkeyPatch) -> Callable[..., None]:
    """Replace the reader, the generator, the speech engine, and the settings."""

    def _wire(
        reader: FakeReader,
        generator: FakeGenerator,
        tts: FakeTTS | None = None,
        storage: FakeStorage | None = None,
        **overrides: Any,
    ) -> None:
        monkeypatch.setattr(ui, "_reader", lambda: reader)
        monkeypatch.setattr(ui, "_generator", lambda: generator)
        if tts is not None:
            monkeypatch.setattr(ui, "_tts", lambda: tts)
        if storage is not None:
            monkeypatch.setattr(ui, "_audio_storage", lambda: storage)
        monkeypatch.setattr(ui, "app_settings", settings(**overrides))

    return _wire


def _stored(session: Session) -> Digest:
    """Return the only stored edition."""
    return session.execute(select(Digest)).scalars().one()


def test_index_lists_the_reports_and_the_creation_form(session: Session, wire: Callable[..., None]) -> None:
    """The home page shows the stored editions and every creation field."""
    wire(FakeReader(), FakeGenerator())
    first = make_report(session, with_audio=True)
    make_report(session)

    response = client.get("/")

    assert response.status_code == 200
    assert response.text.count("<h1") == 1
    assert '<form method="post" action="/ui/reports"' in response.text
    for name in ("period_start", "period_end", "max_entries", "since_last", "tags", "search"):
        assert f'name="{name}"' in response.text
    assert f'href="/reports/{first.id}"' in response.text
    assert "Radar semanal" in response.text
    assert "Con audio" in response.text
    assert "Sin audio" in response.text
    assert "Listo" in response.text


def test_the_form_creates_a_report_through_the_service(session: Session, wire: Callable[..., None]) -> None:
    """The form reaches the report service and redirects to the stored edition."""
    reader = FakeReader([entry(7, "2026-11-23T09:00:00Z")])
    generator = FakeGenerator()
    wire(reader, generator)

    response = client.post("/ui/reports", data=report_form(), follow_redirects=False)

    assert response.status_code == 303
    stored = _stored(session)
    assert response.headers["location"] == f"/reports/{stored.id}"
    assert stored.title == "Radar semanal"
    assert stored.filters["tags"] == ["ai", "modelos"]
    assert stored.filters["search"] == "modelo"
    assert stored.filters["max_entries"] == 5
    assert generator.calls[0]["entries"][0]["entry_id"] == 7

    page = client.get(response.headers["location"])
    assert page.status_code == 200
    assert "Radar semanal" in page.text


def test_a_generation_error_re_renders_the_form(session: Session, wire: Callable[..., None]) -> None:
    """A provider failure keeps the input, explains it in Spanish, and leaks nothing."""
    generator = FakeGenerator()
    generator.error = ReportGenerationError("provider rejected the request with key sk-secret")
    wire(FakeReader([entry(7, "2026-11-23T09:00:00Z")]), generator)

    response = client.post("/ui/reports", data=report_form())

    assert response.status_code == 502
    assert "No se pudo generar el informe" in response.text
    assert "sk-secret" not in response.text
    assert 'value="modelo"' in response.text
    assert '<form method="post" action="/ui/reports"' in response.text


def test_the_report_renders_stories_citations_and_the_synced_player(
    session: Session, wire: Callable[..., None]
) -> None:
    """The edition shows its claims, source links, audio, and segment transcript."""
    wire(FakeReader(), FakeGenerator())
    digest = make_report(session, with_audio=True)
    asset = session.execute(select(AudioAsset)).scalars().one()
    asset.segments = SEGMENTS

    response = client.get(f"/reports/{digest.id}")

    assert response.status_code == 200
    assert response.text.count("<h1") == 1
    assert "Radar semanal" in response.text
    assert "Historia uno" in response.text
    assert "Primera afirmación." in response.text
    assert 'href="https://example.test/uno"' in response.text
    assert "Fuente uno" in response.text
    assert '<audio id="report-audio"' in response.text
    assert 'id="audio-segments"' in response.text
    assert "Introducción a la primera historia." in response.text
    assert '"story_index": 0' in response.text
    assert 'data-story-index="0"' in response.text
    assert 'data-story-seek="0"' in response.text
    assert "Generar audio" not in response.text


def test_a_report_without_audio_offers_generation(session: Session, wire: Callable[..., None]) -> None:
    """The edition has no player and exposes the audio action instead."""
    wire(FakeReader(), FakeGenerator())
    digest = make_report(session)

    response = client.get(f"/reports/{digest.id}")

    assert response.status_code == 200
    assert "Generar audio" in response.text
    assert f'action="/ui/reports/{digest.id}/audio"' in response.text
    assert "<audio" not in response.text


def test_the_audio_action_generates_and_redirects(session: Session, wire: Callable[..., None]) -> None:
    """The audio button synthesizes the edition and returns to it with a notice."""
    storage = FakeStorage()
    wire(FakeReader(), FakeGenerator(), tts=FakeTTS(), storage=storage)
    digest = make_report(session)

    response = client.post(f"/ui/reports/{digest.id}/audio", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == f"/reports/{digest.id}?notice=audio"
    session.refresh(digest)
    assert digest.has_audio is True
    assert len(storage.files) == 1
    page = client.get(response.headers["location"])
    assert "El audio del informe está disponible." in page.text
    assert '<audio id="report-audio"' in page.text


def test_a_tts_error_keeps_the_text_and_offers_a_retry(session: Session, wire: Callable[..., None]) -> None:
    """A speech failure keeps the text edition and the generation action."""
    tts = FakeTTS()
    tts.error = TTSError("engine failed")
    wire(FakeReader(), FakeGenerator(), tts=tts, storage=FakeStorage())
    digest = make_report(session)

    response = client.post(f"/ui/reports/{digest.id}/audio")

    assert response.status_code == 200
    assert "No se pudo generar el audio" in response.text
    assert "sigue disponible" in response.text
    assert "Generar audio" in response.text
    session.refresh(digest)
    assert digest.has_audio is False


def test_an_unknown_report_renders_the_404_page(session: Session, wire: Callable[..., None]) -> None:
    """Reading or voicing a missing edition answers with the Spanish 404 page."""
    wire(FakeReader(), FakeGenerator())

    response = client.get("/reports/999")
    audio = client.post("/ui/reports/999/audio")

    assert response.status_code == 404
    assert response.text.count("<h1") == 1
    assert "No existe ningún informe" in response.text
    assert audio.status_code == 404
    assert "No existe ningún informe" in audio.text


def test_sources_render_the_feeds_with_category_and_last_check(session: Session, wire: Callable[..., None]) -> None:
    """The sources page projects the reader feeds onto the documented columns."""
    feeds = [
        {
            "id": 1,
            "title": "OpenAI",
            "feed_url": "https://openai.test/rss",
            "site_url": "https://openai.test",
            "category": {"id": 1, "title": "Inteligencia artificial"},
            "checked_at": "2026-11-24T10:00:00Z",
            "parsing_error_count": 0,
            "disabled": False,
        }
    ]
    wire(FakeReader(feeds=feeds), FakeGenerator())

    response = client.get("/sources")

    assert response.status_code == 200
    assert response.text.count("<h1") == 1
    assert "OpenAI" in response.text
    assert "Inteligencia artificial" in response.text
    assert "https://openai.test/rss" in response.text
    assert "2026-11-24T10:00:00Z" in response.text
    assert "Activa" in response.text


def test_a_reader_failure_renders_a_message(session: Session, wire: Callable[..., None]) -> None:
    """A reader outage is explained on the page, never as a stack trace."""
    reader = FakeReader()
    reader.error = MinifluxAPIError("dial miniflux failed")
    wire(reader, FakeGenerator())

    response = client.get("/sources")

    assert response.status_code == 502
    assert "No se pudo consultar el lector de fuentes" in response.text
    assert "Volver a intentarlo" in response.text
    assert "dial miniflux failed" not in response.text
    assert "Traceback" not in response.text
