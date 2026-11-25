"""Related coverage persisted by a report and the per-report cost reading."""

import asyncio
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.adapters.llm.openai_report import OpenAIReportGenerator
from app.core.config import Settings
from app.db.base import Base
from app.db.session import get_session
from app.main import app
from app.models import Digest, DigestStory, EntryRelation
from app.schemas.digest import Citation
from app.schemas.digest import Digest as GeneratedDigest
from app.schemas.digest import DigestStory as GeneratedStory
from app.schemas.reports import ReportCreateRequest
from app.services.relations import persist_report_relations, related_entries
from app.services.reporting import ReportService, usage_meta

client = TestClient(app)


def _settings(**overrides: Any) -> Settings:
    """Build settings with the values a unit test does not care about."""
    base: dict[str, Any] = {
        "database_url": "postgresql://test:test@localhost:5432/naf_test",
        "miniflux_url": "http://localhost:8080",
        "miniflux_api_key": "test-token",
        "llm_model": "report-model",
        "llm_api_key": "test-key",
    }
    base.update(overrides)
    return Settings(**base)


@pytest.fixture
def session() -> Iterator[Session]:
    """Yield a session bound to a fresh in-memory database."""
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


def _report_with_two_citations(session: Session) -> Digest:
    """Store one edition whose single story cites two entries."""
    digest = Digest(title="Informe", summary="", filters={}, status="ready", created_at=datetime.now(UTC))
    citation_a = Citation(entry_id="1", entry_url="https://a.test", title="A")
    citation_b = Citation(entry_id="2", entry_url="https://b.test", title="B")
    digest.stories = [
        DigestStory(
            title="Historia",
            claims=["Una afirmación."],
            citations=[citation_a.model_dump(), citation_b.model_dump()],
            order_index=0,
        )
    ]
    session.add(digest)
    session.commit()
    return digest


def test_a_pair_of_citations_becomes_one_relation(session: Session) -> None:
    """The relation is stored once per edition and is symmetric on read."""
    digest = _report_with_two_citations(session)

    assert persist_report_relations(session, digest) == 1
    assert persist_report_relations(session, digest) == 0
    assert session.query(EntryRelation).count() == 1

    assert related_entries(session, 1) == [{"entry_id": 2, "kind": "related", "report_id": digest.id}]
    assert related_entries(session, 2) == [{"entry_id": 1, "kind": "related", "report_id": digest.id}]


def test_a_single_citation_creates_no_relation(session: Session) -> None:
    """One source is not related coverage."""
    digest = Digest(title="Informe", summary="", filters={}, status="ready")
    digest.stories = [
        DigestStory(
            title="Historia",
            claims=["Una afirmación."],
            citations=[Citation(entry_id="1", entry_url="https://a.test", title="A").model_dump()],
            order_index=0,
        )
    ]
    session.add(digest)
    session.commit()

    assert persist_report_relations(session, digest) == 0
    assert related_entries(session, 1) == []


def test_the_related_route_serves_the_pair(session: Session) -> None:
    """A client can read the related coverage through the API."""
    _report_with_two_citations(session)
    persist_report_relations(session, session.query(Digest).one())

    body = client.get("/api/v1/entries/1/related").json()["data"]

    assert body[0]["entry_id"] == 2


def test_the_cost_uses_the_configured_prices() -> None:
    """Tokens are always recorded; the money follows the configured prices."""
    settings = _settings(llm_input_usd_per_1k=1.0, llm_output_usd_per_1k=2.0)

    meta = usage_meta({"prompt_tokens": 1000, "completion_tokens": 500, "total_tokens": 1500}, settings)

    assert meta == {
        "prompt_tokens": 1000,
        "completion_tokens": 500,
        "total_tokens": 1500,
        "cost_usd": 2.0,
    }
    assert usage_meta({"prompt_tokens": 10, "completion_tokens": 5}, _settings())["cost_usd"] == 0.0


def _transport(content: str) -> httpx.MockTransport:
    """Return a transport that answers one chat completion."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": content}}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
            },
        )

    return httpx.MockTransport(handler)


def test_the_adapter_records_the_provider_usage() -> None:
    """One completion reports its tokens on the generated digest."""
    content = (
        '{"title":"Informe","summary":"Resumen","stories":[{"title":"H","summary":"S",'
        '"claims":["C"],"citations":[{"entry_id":"1","quote":null}],"pub_type":"news"}]}'
    )
    generator = OpenAIReportGenerator(_settings(), transport=_transport(content))

    digest = asyncio.run(
        generator.generate(
            [{"entry_id": 1, "url": "https://a.test", "title": "A", "published_at": "2026-11-20T00:00:00Z"}],
            {},
        )
    )

    assert digest.usage == {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}


class _Reader:
    """Minimal reader double: one dated entry."""

    async def get_entries_page(self, **kwargs: Any) -> tuple[list[dict[str, Any]], int]:
        entry = {
            "entry_id": 1,
            "url": "https://a.test",
            "title": "A",
            "published_at": "2026-11-20T00:00:00Z",
            "feed_id": 1,
            "feed_title": "Alfa",
        }
        return [entry], 1


class _Generator:
    """Generator double that reports usage."""

    def __init__(self) -> None:
        self.model = "report-model"

    async def generate(
        self, entries: list[dict[str, Any]], filters: dict[str, Any], since_last: str | None = None
    ) -> GeneratedDigest:
        story = GeneratedStory(
            title="Historia",
            summary="Resumen",
            claims=["Una afirmación."],
            citations=[Citation(entry_id="1", entry_url="https://a.test", title="A")],
            pub_type="news",
        )
        return GeneratedDigest(
            title="Informe",
            summary="Resumen",
            period_start="2026-11-20T00:00:00+00:00",
            period_end="2026-11-20T00:00:00+00:00",
            stories=[story],
            usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
        )

    def validate_citations(self, digest: GeneratedDigest, entries: list[dict[str, Any]]) -> bool:
        return True


def test_a_stored_edition_keeps_the_cost_meta(session: Session) -> None:
    """The edition records the tokens and the cost the settings imply."""
    settings = _settings(llm_input_usd_per_1k=1.0, llm_output_usd_per_1k=2.0)
    service = ReportService(session, _Reader(), _Generator(), settings)

    async def run() -> Digest:
        return await service.create(ReportCreateRequest())

    report = asyncio.run(run())

    assert report.meta["prompt_tokens"] == 100
    assert report.meta["completion_tokens"] == 50
    assert report.meta["cost_usd"] == 0.2
