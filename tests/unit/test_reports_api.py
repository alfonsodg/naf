"""The report API: generation, the Spanish no-news outcome, and the saved history.

A fake reader stands in for Miniflux and a fake generator for the LLM provider,
so these tests exercise selection, persistence, and the HTTP contract without a
network call or a real model.
"""

from collections.abc import Callable, Iterator
from datetime import datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import Settings
from app.core.exceptions import ReportGenerationError
from app.db.base import Base
from app.db.session import get_session
from app.main import app
from app.models import Digest
from app.routers import reports
from app.schemas.digest import Citation, DigestStory
from app.schemas.digest import Digest as GeneratedDigest

client = TestClient(app)


def _settings(**overrides: Any) -> Settings:
    """Build settings with the deployment values a test does not care about."""
    base: dict[str, Any] = {
        "database_url": "postgresql://test:test@localhost:5432/naf_test",
        "miniflux_url": "http://localhost:8080",
        "miniflux_api_key": "test-token",
        "llm_model": overrides.pop("llm_model", "report-model"),
        **overrides,
    }
    return Settings(**base)


def _entry(entry_id: int, published: str) -> dict[str, Any]:
    """Build one normalized entry with its provenance."""
    return {
        "entry_id": entry_id,
        "url": f"https://example.test/{entry_id}",
        "title": f"Entrada {entry_id}",
        "published_at": published,
        "feed_id": 1,
        "feed_title": "Alpha",
    }


def _published(entry: dict[str, Any]) -> datetime:
    """Read the publication instant of a fake entry."""
    return datetime.fromisoformat(str(entry["published_at"]).replace("Z", "+00:00"))


class _FakeReader:
    """Reader double that honors the publication cutoff and records every call."""

    def __init__(self, entries: list[dict[str, Any]]) -> None:
        self.entries = entries
        self.calls: list[dict[str, Any]] = []

    async def get_entries_page(self, **kwargs: Any) -> tuple[list[dict[str, Any]], int]:
        """Return the entries published after the requested cutoff."""
        self.calls.append(kwargs)
        after = kwargs.get("published_after")
        selected = [entry for entry in self.entries if after is None or _published(entry) > after]
        return selected, len(selected)


class _FakeGenerator:
    """Generator double that records the selection and can fail on demand."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.error: Exception | None = None
        self.invalid = False

    async def generate(
        self,
        entries: list[dict[str, Any]],
        filters: dict[str, Any],
        since_last: str | None = None,
    ) -> GeneratedDigest:
        """Build one story that cites the first selected entry."""
        self.calls.append({"entries": entries, "filters": filters, "since_last": since_last})
        if self.error is not None:
            raise self.error
        first = entries[0]
        story = DigestStory(
            title="Historia del periodo",
            summary="Resumen en español con atribución.",
            claims=["La entrada publica una novedad."],
            citations=[Citation(entry_id=str(first["entry_id"]), entry_url=first["url"], title=first["title"])],
            pub_type="news",
            official=True,
            uncertainties=["El alcance no consta en las entradas."],
        )
        return GeneratedDigest(
            title="Radar semanal",
            summary="Resumen del periodo seleccionado.",
            period_start="2026-11-18T00:00:00+00:00",
            period_end="2026-11-24T00:00:00+00:00",
            filters=filters,
            stories=[story],
        )

    def validate_citations(self, digest: GeneratedDigest, entries: list[dict[str, Any]]) -> bool:
        """Report the configured citation verdict."""
        return not self.invalid


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
def wire(monkeypatch: pytest.MonkeyPatch) -> Callable[..., None]:
    """Replace the reader, the generator, and the settings the routes build."""

    def _wire(reader: _FakeReader, generator: _FakeGenerator, **settings: Any) -> None:
        monkeypatch.setattr(reports, "_reader", lambda: reader)
        monkeypatch.setattr(reports, "_generator", lambda: generator)
        monkeypatch.setattr(reports, "app_settings", _settings(**settings))

    return _wire


def _post(payload: dict[str, Any]) -> Any:
    """Create one report through the API."""
    return client.post("/api/v1/reports", json=payload)


def _stored(session: Session) -> Digest:
    """Return the most recently stored edition."""
    row = session.execute(select(Digest).order_by(Digest.id.desc())).scalars().first()
    assert row is not None
    return row


def test_a_report_is_served_and_stored_with_its_stories(session: Session, wire: Callable[..., None]) -> None:
    """The edition keeps its entries, cursor, metadata, and cited stories."""
    reader = _FakeReader([_entry(2, "2026-11-23T09:00:00Z"), _entry(1, "2026-11-22T09:00:00Z")])
    generator = _FakeGenerator()
    wire(reader, generator)

    response = _post({})

    assert response.status_code == 201
    body = response.json()["data"]
    assert body["status"] == "ready"
    assert body["title"] == "Radar semanal"
    assert body["entry_ids"] == [2, 1]
    assert body["cursor"] == "2026-11-23T09:00:00+00:00"
    assert body["version"] == "1.0"
    assert body["meta"] == {"model": "report-model", "prompt_version": "1.1", "entry_count": 2}
    assert [entry["entry_id"] for entry in generator.calls[0]["entries"]] == [2, 1]

    detail = client.get(f"/api/v1/reports/{body['report_id']}").json()["data"]
    assert detail["stories"][0]["claims"] == ["La entrada publica una novedad."]
    assert detail["stories"][0]["citations"][0]["entry_id"] == "2"
    assert detail["stories"][0]["official"] is True
    assert detail["stories"][0]["uncertainties"] == ["El alcance no consta en las entradas."]
    stored_story = _stored(session).stories[0]
    assert stored_story.official is True
    assert stored_story.uncertainties == ["El alcance no consta en las entradas."]
    assert len(_stored(session).stories) == 1


def test_a_raw_reader_entry_is_projected_before_the_generator(session: Session, wire: Callable[..., None]) -> None:
    """The reader returns its own document; the generator needs the NAF shape."""
    raw = {
        "id": 77,
        "url": "https://beta.test/77",
        "title": "Entrada cruda",
        "published_at": "2026-11-23T09:00:00Z",
        "feed": {"id": 2, "title": "Beta", "feed_url": "https://beta.test/rss", "site_url": "https://beta.test"},
    }
    generator = _FakeGenerator()
    wire(_FakeReader([raw]), generator)

    response = _post({})

    assert response.status_code == 201
    selected = generator.calls[0]["entries"][0]
    assert selected["entry_id"] == 77
    assert selected["feed_title"] == "Beta"
    assert _stored(session).entry_ids == [77]


def test_an_empty_selection_is_stored_as_no_news(session: Session, wire: Callable[..., None]) -> None:
    """No entries produce the explicit Spanish message and no model call."""
    generator = _FakeGenerator()
    wire(_FakeReader([]), generator)

    response = _post({"period_start": "2026-11-18T00:00:00Z", "period_end": "2026-11-24T00:00:00Z"})

    assert response.status_code == 201
    body = response.json()["data"]
    assert body["status"] == "no_news"
    assert body["title"] == "Sin novedades"
    assert "No hay entradas nuevas" in body["summary"]
    assert body["entry_ids"] == []
    assert generator.calls == []
    assert "No hay entradas nuevas" in str(_stored(session).summary)


def test_a_failed_generation_is_stored_and_answered(session: Session, wire: Callable[..., None]) -> None:
    """A provider error and an invalid citation answer 502 and leave a failed edition."""
    provider = _FakeGenerator()
    provider.error = ReportGenerationError("provider rejected key sk-secret")
    wire(_FakeReader([_entry(1, "2026-11-23T09:00:00Z")]), provider, llm_api_key="sk-secret")

    response = _post({})

    assert response.status_code == 502
    assert response.json()["detail"]["error"]["code"] == "REPORT_GENERATION_FAILED"
    assert "sk-secret" not in response.text
    failed = _stored(session)
    assert failed.status == "failed"
    assert failed.error_summary is not None and "provider rejected" in failed.error_summary
    assert "sk-secret" not in failed.error_summary

    invalid = _FakeGenerator()
    invalid.invalid = True
    wire(_FakeReader([_entry(1, "2026-11-23T09:00:00Z")]), invalid)

    assert _post({}).json()["detail"]["error"]["code"] == "REPORT_CITATIONS_INVALID"
    assert _stored(session).status == "failed"


def test_an_unconfigured_model_is_refused(wire: Callable[..., None]) -> None:
    """An empty model answers 503 and neither reads entries nor builds a report."""
    reader = _FakeReader([_entry(1, "2026-11-23T09:00:00Z")])
    generator = _FakeGenerator()
    wire(reader, generator, llm_model="")

    response = _post({})

    assert response.status_code == 503
    assert response.json()["detail"]["error"]["code"] == "REPORT_GENERATOR_NOT_CONFIGURED"
    assert reader.calls == []
    assert generator.calls == []


def test_the_history_is_paginated_newest_first(session: Session, wire: Callable[..., None]) -> None:
    """The list orders by recency and paginates; an unknown edition is a 404."""
    wire(_FakeReader([_entry(1, "2026-11-23T09:00:00Z")]), _FakeGenerator())
    created = [_post({}).json()["data"]["report_id"] for _ in range(3)]

    response = client.get("/api/v1/reports", params={"per_page": 2})

    assert response.status_code == 200
    body = response.json()
    assert [row["report_id"] for row in body["data"]] == [created[2], created[1]]
    assert body["pagination"] == {"page": 1, "per_page": 2, "total": 3, "total_pages": 2}
    assert len(client.get(f"/api/v1/reports/{created[0]}").json()["data"]["stories"]) == 1
    missing = client.get("/api/v1/reports/999")
    assert missing.status_code == 404
    assert missing.json()["detail"]["error"]["code"] == "REPORT_NOT_FOUND"


def test_since_last_uses_the_newest_cursor(session: Session, wire: Callable[..., None]) -> None:
    """The second edition starts after the first cursor and includes only what arrived."""
    reader = _FakeReader([_entry(1, "2026-11-21T09:00:00Z"), _entry(2, "2026-11-22T09:00:00Z")])
    generator = _FakeGenerator()
    wire(reader, generator)
    first = _post({}).json()["data"]
    reader.entries.append(_entry(3, "2026-11-23T09:00:00Z"))

    second = _post({"since_last": True}).json()["data"]

    assert second["entry_ids"] == [3]
    assert first["cursor"] == "2026-11-22T09:00:00+00:00"
    assert generator.calls[1]["since_last"] == first["cursor"]
    assert reader.calls[1]["published_after"].isoformat() == first["cursor"]


def test_the_entry_cap_is_enforced(session: Session, wire: Callable[..., None]) -> None:
    """A request cannot exceed the configured selection size."""
    reader = _FakeReader([_entry(identifier, f"2026-11-2{identifier}T09:00:00Z") for identifier in range(1, 4)])
    generator = _FakeGenerator()
    wire(reader, generator, report_max_entries=2)

    _post({"max_entries": 5})
    _post({"max_entries": 1})

    assert len(generator.calls[0]["entries"]) == 2
    assert len(generator.calls[1]["entries"]) == 1
    assert reader.calls[0]["limit"] == 2


def test_the_selection_filters_are_forwarded_to_the_reader(session: Session, wire: Callable[..., None]) -> None:
    """Feeds, categories, tags, search, and state reach the reader unchanged."""
    reader = _FakeReader([_entry(1, "2026-11-23T09:00:00Z")])
    wire(reader, _FakeGenerator())

    _post({"feed_ids": [3, 4], "tags": ["ai", "models"], "search": "modelo", "read": False, "starred": True})
    _post({"category_ids": [7, 8]})

    assert [call["feed_id"] for call in reader.calls[:2]] == [3, 4]
    assert [call["category_id"] for call in reader.calls[2:]] == [7, 8]
    assert reader.calls[0]["tags"] == ["ai", "models"]
    assert reader.calls[0]["search"] == "modelo"
    assert reader.calls[0]["read"] is False
    assert reader.calls[0]["starred"] is True
