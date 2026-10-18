from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any


class FeedReader(ABC):
    @abstractmethod
    async def health(self) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def list_feeds(self) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    async def get_entries(
        self,
        feed_id: Optional[int] = None,
        limit: int = 100,
        offset: int = 0,
        category_id: Optional[int] = None,
        starred: Optional[bool] = None,
        read: Optional[bool] = None,
        search: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    async def get_entry(self, entry_id: int) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def mark_entry_read(self, entry_id: int) -> bool:
        pass

    @abstractmethod
    async def export_opml(self) -> str:
        pass

    @abstractmethod
    async def import_opml(self, opml_content: str) -> Dict[str, Any]:
        pass
