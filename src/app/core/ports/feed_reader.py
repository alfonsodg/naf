"""Reader port. Reader state is owned by Miniflux, never by NAF."""

from abc import ABC, abstractmethod
from typing import Any


class FeedReader(ABC):
    """Read and update reader state through a remote API."""

    @abstractmethod
    async def health(self) -> dict[str, Any]:
        """Return the reader health status."""

    @abstractmethod
    async def list_feeds(self) -> list[dict[str, Any]]:
        """List every configured feed with its health metadata."""

    @abstractmethod
    async def get_entries(
        self,
        feed_id: int | None = None,
        limit: int = 100,
        offset: int = 0,
        category_id: int | None = None,
        starred: bool | None = None,
        read: bool | None = None,
        search: str | None = None,
    ) -> list[dict[str, Any]]:
        """List entries honoring every optional filter."""

    @abstractmethod
    async def get_entries_page(
        self,
        feed_id: int | None = None,
        limit: int = 100,
        offset: int = 0,
        category_id: int | None = None,
        starred: bool | None = None,
        read: bool | None = None,
        search: str | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        """List one page of entries and report the unpaginated total."""

    @abstractmethod
    async def get_entry(self, entry_id: int) -> dict[str, Any]:
        """Fetch one entry by its reader identifier."""

    @abstractmethod
    async def update_entries_status(self, entry_ids: list[int], status: str) -> bool:
        """Set the read status for one or more entries."""

    @abstractmethod
    async def mark_entry_read(self, entry_id: int) -> bool:
        """Mark one entry as read."""

    @abstractmethod
    async def export_opml(self) -> str:
        """Export subscriptions as an OPML document."""

    @abstractmethod
    async def import_opml(self, opml_content: str) -> dict[str, Any]:
        """Import subscriptions from an OPML document."""
