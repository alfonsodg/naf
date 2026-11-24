"""OpenAI-compatible report generator: citations, repair, and prompt bounds."""

import json
import re
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest

from app.adapters.llm.openai_report import PROMPT_CHAR_BUDGET, OpenAIReportGenerator
from app.core.config import Settings
from app.core.exceptions import CitationValidationError, ReportGenerationError
from app.schemas.digest import Citation, Digest, DigestStory

ENTRIES: list[dict[str, Any]] = [
    {
        "entry_id": 101,
        "title": "El equipo X publica el modelo X",
        "author": "Equipo X",
        "url": "https://example.test/x",
        "feed_title": "Blog de X",
        "published_at": "2026-11-20T10:00:00Z",
        "tags": [{"title": "modelos"}],
        "content": "El equipo X publicó el modelo X con pesos abiertos.",
    },
    {
        "entry_id": "102",
        "title": "Análisis independiente del modelo X",
        "author": "Analista",
        "url": "https://example.test/analisis",
        "feed_title": "Análisis",
        "published_at": "2026-11-21T09:30:00Z",
        "tags": ["modelos"],
        "content": "Una lectura de terceros sobre el modelo X.",
    },
]


def _settings(**overrides: Any) -> Settings:
    """Build settings with the deployment values a test does not exercise."""
    base: dict[str, Any] = {
        "database_url": "postgresql://test:test@localhost:5432/naf_test",
        "miniflux_url": "http://localhost:8080",
        "miniflux_api_key": "test-token",
        "llm_base_url": "https://provider.test/v1",
        "llm_model": "report-model",
        "llm_api_key": "test-key",
    }
    base.update(overrides)
    return Settings(**base)


def _story(**overrides: Any) -> dict[str, Any]:
    """Build one valid story of the model answer."""
    story: dict[str, Any] = {
        "title": "El modelo X llega con pesos abiertos",
        "summary": "El equipo X publicó el modelo X y la cobertura independiente lo analiza.",
        "claims": ["El equipo X publicó el modelo X con pesos abiertos."],
        "citations": [
            {"entry_id": 101, "quote": "pesos abiertos"},
            {"entry_id": "102", "quote": None},
        ],
        "pub_type": "release",
        "official": True,
    }
    story.update(overrides)
    return story


def _report(story: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build one valid model answer."""
    return {"title": "Informe del periodo", "summary": "Resumen del periodo.", "stories": [story or _story()]}


def _completion(payload: Any) -> httpx.Response:
    """Wrap a model answer as a chat completion response."""
    content = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
    return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})


def _transport(
    responses: list[httpx.Response],
) -> tuple[httpx.MockTransport, list[httpx.Request], list[dict[str, Any]]]:
    """Serve queued answers while recording every request and its payload."""
    requests: list[httpx.Request] = []
    payloads: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        payloads.append(json.loads(request.content))
        return responses[min(len(requests), len(responses)) - 1]

    return httpx.MockTransport(handler), requests, payloads


async def test_a_valid_answer_becomes_a_digest_with_authoritative_citations() -> None:
    """URL, title and author come from the stored entry, not from the model."""
    transport, requests, payloads = _transport([_completion(_report())])
    generator = OpenAIReportGenerator(_settings(), transport)

    digest = await generator.generate(ENTRIES, {"tags": ["modelos"]}, since_last="2026-11-19T00:00:00Z")

    assert len(requests) == 1
    assert str(requests[0].url) == "https://provider.test/v1/chat/completions"
    assert payloads[0]["model"] == "report-model"
    assert payloads[0]["temperature"] == 0.2
    assert payloads[0]["max_tokens"] == _settings().llm_max_output_tokens
    assert payloads[0]["messages"][0]["role"] == "system"
    assert digest.title == "Informe del periodo"
    assert digest.filters == {"tags": ["modelos"]}
    assert digest.period_start == "2026-11-20T10:00:00+00:00"
    assert digest.period_end == "2026-11-21T09:30:00+00:00"
    assert digest.stories[0].pub_type == "release"
    citations = digest.stories[0].citations
    assert [citation.entry_id for citation in citations] == ["101", "102"]
    assert [citation.entry_url for citation in citations] == [ENTRIES[0]["url"], ENTRIES[1]["url"]]
    assert [citation.title for citation in citations] == [ENTRIES[0]["title"], ENTRIES[1]["title"]]
    assert [citation.author for citation in citations] == ["Equipo X", "Analista"]
    assert citations[0].quote == "pesos abiertos"


async def test_an_unknown_citation_id_triggers_one_repair_call() -> None:
    """A repair repeats the entries and lists the unresolved identifier."""
    invalid = _report(_story(citations=[{"entry_id": "999", "quote": None}]))
    transport, requests, payloads = _transport([_completion(invalid), _completion(_report())])
    generator = OpenAIReportGenerator(_settings(), transport)

    digest = await generator.generate(ENTRIES, {})

    assert len(requests) == 2
    repair = payloads[1]["messages"][1]["content"]
    assert "entry_id=999" in repair
    assert "ausente de la lista" in repair
    assert "entry_id=101" in repair
    assert digest.stories[0].citations[0].entry_id == "101"


async def test_citations_that_remain_invalid_raise_after_one_repair() -> None:
    """Two invalid answers never produce a digest."""
    invalid = _report(_story(citations=[{"entry_id": "999", "quote": None}]))
    transport, requests, _ = _transport([_completion(invalid), _completion(invalid)])
    generator = OpenAIReportGenerator(_settings(), transport)

    with pytest.raises(CitationValidationError, match="999"):
        await generator.generate(ENTRIES, {})

    assert len(requests) == 2


async def test_a_provider_failure_raises_a_generation_error() -> None:
    """An HTTP failure is reported as a generation error, without a repair."""
    transport = httpx.MockTransport(lambda request: httpx.Response(500, text="boom"))
    generator = OpenAIReportGenerator(_settings(), transport)

    with pytest.raises(ReportGenerationError, match="500"):
        await generator.generate(ENTRIES, {})


async def test_a_provider_that_rejects_response_format_is_retried_without_it() -> None:
    """The retry repeats the request once and drops only response_format."""
    payloads: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        payloads.append(payload)
        if "response_format" in payload:
            return httpx.Response(400, json={"error": {"message": "response_format is not supported"}})
        return _completion(_report())

    generator = OpenAIReportGenerator(_settings(), httpx.MockTransport(handler))

    digest = await generator.generate(ENTRIES, {})

    assert len(payloads) == 2
    assert "response_format" in payloads[0]
    assert "response_format" not in payloads[1]
    assert payloads[1]["model"] == payloads[0]["model"]
    assert digest.stories[0].citations[0].entry_id == "101"


async def test_malformed_json_is_repaired_once() -> None:
    """One broken answer is tolerated when the repair returns valid JSON."""
    transport, requests, _ = _transport([_completion("{esto no es json"), _completion(_report())])
    generator = OpenAIReportGenerator(_settings(), transport)

    digest = await generator.generate(ENTRIES, {})

    assert len(requests) == 2
    assert digest.stories[0].citations[0].entry_id == "101"


async def test_malformed_json_that_survives_the_repair_raises() -> None:
    """Two broken answers are a generation error, not a partial digest."""
    transport, requests, _ = _transport([_completion("no json"), _completion("sigue sin ser json")])
    generator = OpenAIReportGenerator(_settings(), transport)

    with pytest.raises(ReportGenerationError, match="valid JSON"):
        await generator.generate(ENTRIES, {})

    assert len(requests) == 2


async def test_a_non_empty_selection_without_stories_is_an_error() -> None:
    """The no-news answer is only valid for an empty selection."""
    transport, _, _ = _transport([_completion({"title": "Sin novedades", "summary": "Nada", "stories": []})])
    generator = OpenAIReportGenerator(_settings(), transport)

    with pytest.raises(ReportGenerationError, match="no stories"):
        await generator.generate(ENTRIES, {})


async def test_the_prompt_carries_only_the_selection_and_respects_the_budget() -> None:
    """The oldest entries are dropped once the entry blocks exceed the budget."""
    entries = [
        {
            "entry_id": index,
            "title": f"Entrada {index}",
            "url": f"https://example.test/{index}",
            "published_at": (datetime(2026, 11, 1, tzinfo=UTC) + timedelta(minutes=index)).isoformat(),
            "content": "x" * 900,
        }
        for index in range(1, 81)
    ]
    newest = entries[-1]["entry_id"]
    answer = _report(_story(citations=[{"entry_id": newest, "quote": None}]))
    transport, requests, payloads = _transport([_completion(answer)])
    generator = OpenAIReportGenerator(_settings(), transport)

    digest = await generator.generate(entries, {"tags": ["modelos"]}, since_last="2026-11-01T00:00:00Z")

    prompt = payloads[0]["messages"][1]["content"]
    assert len(requests) == 1
    assert len(prompt) < PROMPT_CHAR_BUDGET + 2_000
    assert {int(found) for found in re.findall(r"entry_id=(\d+)", prompt)} <= {entry["entry_id"] for entry in entries}
    assert f"entry_id={newest}\n" in prompt
    assert "entry_id=1\n" not in prompt
    assert "Se omitieron" in prompt
    assert "Desde el último informe: 2026-11-01T00:00:00Z" in prompt
    assert digest.stories[0].citations[0].entry_id == str(newest)


async def test_an_empty_selection_returns_no_news_without_a_provider_call() -> None:
    """Nothing selected means an explicit empty report, never a filler story."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("the provider must not be called")

    generator = OpenAIReportGenerator(_settings(), httpx.MockTransport(handler))

    digest = await generator.generate([], {"feed_id": 3})

    assert digest.title == "Sin novedades"
    assert digest.stories == []
    assert digest.filters == {"feed_id": 3}


@pytest.mark.parametrize("overrides", [{"llm_model": ""}, {"llm_api_key": ""}])
async def test_an_unconfigured_generator_never_calls_the_provider(overrides: dict[str, str]) -> None:
    """A missing model or key fails before any network access."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("the provider must not be called")

    generator = OpenAIReportGenerator(_settings(**overrides), httpx.MockTransport(handler))

    with pytest.raises(ReportGenerationError, match="not configured"):
        await generator.generate(ENTRIES, {})


def test_validate_citations_checks_identifiers_and_claims() -> None:
    """A digest is citable only when every story has claims and a known source."""
    digest = Digest(
        title="Informe",
        summary="Resumen",
        period_start="2026-11-20T00:00:00Z",
        period_end="2026-11-21T00:00:00Z",
        stories=[
            DigestStory(
                title="El modelo X",
                summary="Resumen",
                claims=["El equipo X publicó el modelo X."],
                citations=[Citation(entry_id="101", entry_url="https://example.test/x", title="El modelo X")],
            )
        ],
    )
    generator = OpenAIReportGenerator(_settings(), httpx.MockTransport(lambda request: httpx.Response(500)))

    assert generator.validate_citations(digest, ENTRIES) is True
    digest.stories[0].citations[0].entry_id = "999"
    assert generator.validate_citations(digest, ENTRIES) is False
    digest.stories[0].citations[0].entry_id = "101"
    digest.stories[0].claims = []
    assert generator.validate_citations(digest, ENTRIES) is False
