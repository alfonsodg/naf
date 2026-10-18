"""Classification port."""

from abc import ABC, abstractmethod
from typing import Any

from app.schemas.classification import Classification


class Classifier(ABC):
    """Assign categories and tags to reader items."""

    @abstractmethod
    async def classify(self, item: dict[str, Any]) -> Classification:
        """Classify a single item."""

    @abstractmethod
    async def classify_batch(self, items: list[dict[str, Any]]) -> list[Classification]:
        """Classify several items preserving input order."""
