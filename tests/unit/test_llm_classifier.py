"""The LLM classifier: one repair, literal evidence, and provider failures."""

import json
from typing import Any

import httpx
import pytest

from app.adapters.llm.classifier import LLMClassifier
from app.core.config import Settings
from app.core.exceptions import ClassificationError

ENTRY: dict[str, Any] = {
    "entry_id": 10,
    "title": "El equipo X publica Modelo X",
    "url": "https://creator.test/model-x",
    "feed_title": "Blog del equipo X",
    "published_at": "2026-11-20T10:00:00Z",
    "author": "Equipo X",
    "content": "<p>El equipo X anuncia el lanzamiento de Modelo X con pesos abiertos.</p>",
    "tags": [{"name": "modelos"}],
}

ANSWER: dict[str, Any] = {
    "category": "Tecnología y software",
    "categories": ["Tecnología y software", "IA y modelos"],
    "tags": ["modelos", "lanzamiento"],
    "pub_type": "announcement",
    "is_official": True,
    "confidence": 0.9,
    "uncertainty": False,
    "review_needed": False,
    "rationale": "La entrada anuncia un lanzamiento en el canal del creador.",
    "models": [
        {
            "name": "Modelo X",
            "creator": "Equipo X",
            "change_type": "new_model",
            "official": True,
            "evidence_quote": "anuncia el lanzamiento de Modelo X",
            "evidence_url": "https://creator.test/model-x",
            "confidence": 0.95,
        }
    ],
}


def _settings(**overrides: Any) -> Settings:
    """Build settings with the deployment values a test does not exercise."""
    base: dict[str, Any] = {
        "database_url": "postgresql://test:test@localhost:5432/naf_test",
        "miniflux_url": "http://localhost:8080",
        "miniflux_api_key": "test-token",
        "llm_base_url": "https://provider.test/v1",
        "llm_model": "classifier-model",
        "llm_api_key": "test-key",
    }
    base.update(overrides)
    return Settings(**base)


def _completion(payload: Any) -> httpx.Response:
    """Wrap a model answer as a chat completion response."""
    content = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
    return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})


def _transport(responses: list[httpx.Response]) -> tuple[httpx.MockTransport, list[dict[str, Any]]]:
    """Serve queued answers while recording every request payload."""
    payloads: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payloads.append(json.loads(request.content))
        return responses[min(len(payloads), len(responses)) - 1]

    return httpx.MockTransport(handler), payloads


async def test_a_valid_answer_becomes_a_classification_with_literal_evidence() -> None:
    """The answer maps onto the contract and keeps the quote the entry contains."""
    transport, payloads = _transport([_completion(ANSWER)])
    classifier = LLMClassifier(_settings(), transport)

    result = await classifier.classify(ENTRY)

    assert result.category == "Tecnología y software"
    assert result.categories == ["Tecnología y software", "IA y modelos"]
    assert result.is_official is True
    assert result.confidence == 0.9
    assert result.models[0].name == "Modelo X"
    assert result.models[0].change_type == "new_model"
    assert result.models[0].official is True
    assert result.models[0].evidence_quote == "anuncia el lanzamiento de Modelo X"
    assert payloads[0]["model"] == "classifier-model"
    assert payloads[0]["temperature"] == 0.0
    assert payloads[0]["messages"][0]["role"] == "system"
    assert "evidence_quote" in payloads[0]["messages"][0]["content"]


async def test_a_quote_the_entry_does_not_contain_is_dropped() -> None:
    """An invented quote never becomes stored evidence."""
    answer = {**ANSWER, "models": [{**ANSWER["models"][0], "evidence_quote": "un fragmento inventado"}]}
    transport, _ = _transport([_completion(answer)])
    classifier = LLMClassifier(_settings(), transport)

    result = await classifier.classify(ENTRY)

    assert result.models[0].evidence_quote == ""
    assert result.models[0].name == "Modelo X"


async def test_an_invalid_answer_is_repaired_once() -> None:
    """One broken answer is tolerated when the repair returns valid JSON."""
    transport, payloads = _transport([_completion("{esto no es json"), _completion(ANSWER)])
    classifier = LLMClassifier(_settings(), transport)

    result = await classifier.classify(ENTRY)

    assert len(payloads) == 2
    repair = payloads[1]["messages"][1]["content"]
    assert "no es un JSON válido" in repair
    assert "Clasifica esta entrada" in repair
    assert result.category == "Tecnología y software"


async def test_two_invalid_answers_raise_a_classification_error() -> None:
    """A second invalid answer is refused instead of inventing a classification."""
    transport, payloads = _transport([_completion("no json"), _completion("sigue sin ser json")])
    classifier = LLMClassifier(_settings(), transport)

    with pytest.raises(ClassificationError, match="valid answer"):
        await classifier.classify(ENTRY)

    assert len(payloads) == 2


async def test_a_provider_failure_is_a_classification_error() -> None:
    """A status failure surfaces as the classifier's own error, without a repair."""
    transport = httpx.MockTransport(lambda request: httpx.Response(500, text="boom"))
    classifier = LLMClassifier(_settings(), transport)

    with pytest.raises(ClassificationError, match="500"):
        await classifier.classify(ENTRY)


async def test_an_answer_without_models_is_valid() -> None:
    """An entry that names no model keeps an explicit empty mention list."""
    answer = {**ANSWER, "models": []}
    transport, _ = _transport([_completion(answer)])
    classifier = LLMClassifier(_settings(), transport)

    result = await classifier.classify(ENTRY)

    assert result.models == []
    assert result.review_needed is False


async def test_classify_batch_preserves_the_input_order() -> None:
    """The batch path classifies one entry at a time and keeps their order."""
    transport, payloads = _transport([_completion(ANSWER), _completion({**ANSWER, "category": "Ciencia y espacio"})])
    classifier = LLMClassifier(_settings(), transport)

    results = await classifier.classify_batch([ENTRY, ENTRY])

    assert len(payloads) == 2
    assert [result.category for result in results] == ["Tecnología y software", "Ciencia y espacio"]
