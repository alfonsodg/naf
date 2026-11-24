"""Classification port."""

from abc import ABC, abstractmethod
from typing import Any

from app.schemas.classification import Classification


class Classifier(ABC):
    """Assign categories, tags, and evidence-backed model mentions to reader items."""

    @property
    def model(self) -> str:
        """Identify the model behind the classifier; empty when it does not apply."""
        return ""

    @abstractmethod
    async def classify(self, item: dict[str, Any]) -> Classification:
        """Classify a single item."""

    @abstractmethod
    async def classify_batch(self, items: list[dict[str, Any]]) -> list[Classification]:
        """Classify several items preserving input order."""
