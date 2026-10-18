"""Report generation port. Every factual claim requires a citation."""

from abc import ABC, abstractmethod
from typing import Any

from app.schemas.digest import Digest


class ReportGenerator(ABC):
    """Turn selected entries into a cited digest."""

    @abstractmethod
    async def generate(
        self,
        entries: list[dict[str, Any]],
        filters: dict[str, Any],
        since_last: str | None = None,
    ) -> Digest:
        """Build a digest from the selected entries."""

    @abstractmethod
    def validate_citations(self, digest: Digest, entries: list[dict[str, Any]]) -> bool:
        """Confirm every claim resolves to a real source entry."""
