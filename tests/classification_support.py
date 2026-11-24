"""Doubles shared by the classification test modules.

They stay outside a ``test_`` module so pytest never collects them, and every
classification suite imports the same reader, classifier, and settings builder.
"""

from typing import Any

from app.core.config import Settings
from app.core.exceptions import MinifluxAPIError
from app.core.ports.classifier import Classifier
from app.schemas.classification import Classification, ModelMention

ENTRY: dict[str, Any] = {
    "id": 10,
    "url": "https://creator.test/model-x",
    "title": "El equipo X publica Modelo X",
    "content": "<p>El equipo X anuncia el lanzamiento de Modelo X con pesos abiertos.</p>",
    "published_at": "2026-11-20T10:00:00Z",
    "tags": [{"id": 3, "name": "modelos"}],
    "feed": {"id": 1, "title": "Blog del equipo X", "feed_url": "https://creator.test/rss"},
}


def settings_with(**overrides: Any) -> Settings:
    """Build settings with the deployment values a test does not exercise."""
    base: dict[str, Any] = {
        "database_url": "postgresql://test:test@localhost:5432/naf_test",
        "miniflux_url": "http://localhost:8080",
        "miniflux_api_key": "test-token",
        "llm_model": "classifier-model",
    }
    base.update(overrides)
    return Settings(**base)


class FakeReader:
    """Reader double that returns one entry or reports it as unknown."""

    def __init__(self, missing: bool = False) -> None:
        self.missing = missing
        self.entry = ENTRY
        self.calls: list[int] = []

    async def get_entry(self, entry_id: int) -> dict[str, Any]:
        """Return the stored entry or the reader's 404."""
        self.calls.append(entry_id)
        if self.missing:
            raise MinifluxAPIError(f"Miniflux /v1/entries/{entry_id} returned 404", status_code=404)
        return self.entry


class FakeClassifier(Classifier):
    """Classifier double that records every call and can fail on demand."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.error: Exception | None = None

    @property
    def model(self) -> str:
        """Return the model identifier the stored row must record."""
        return "classifier-model"

    async def classify(self, item: dict[str, Any]) -> Classification:
        """Return one evidence-backed classification for the entry."""
        self.calls.append(item)
        if self.error is not None:
            raise self.error
        return Classification(
            category="Tecnología y software",
            categories=["Tecnología y software", "IA y modelos"],
            tags=["modelos", "lanzamiento"],
            pub_type="announcement",
            is_official=True,
            confidence=0.9,
            uncertainty=False,
            review_needed=False,
            rationale="La entrada anuncia el lanzamiento en el canal del creador.",
            models=[
                ModelMention(
                    name="Modelo X",
                    creator="Equipo X",
                    change_type="new_model",
                    official=True,
                    evidence_quote="anuncia el lanzamiento de Modelo X",
                    evidence_url="https://creator.test/model-x",
                    confidence=0.95,
                )
            ],
        )

    async def classify_batch(self, items: list[dict[str, Any]]) -> list[Classification]:
        """Classify every item through the same recorded path."""
        return [await self.classify(item) for item in items]
