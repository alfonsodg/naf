from typing import List, Dict, Any
from app.contracts.feed_reader import FeedReader


class Collector:
    def __init__(self, feed_reader: FeedReader):
        self.feed_reader = feed_reader

    async def sync_feeds(self) -> Dict[str, Any]:
        # TODO: Implement actual sync logic
        feeds = await self.feed_reader.list_feeds()
        return {"feeds_count": len(feeds), "status": "ok"}

    async def get_entries(self, **kwargs) -> List[Dict[str, Any]]:
        return await self.feed_reader.get_entries(**kwargs)
