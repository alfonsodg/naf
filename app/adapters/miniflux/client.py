from typing import List, Optional, Dict, Any
import httpx

from app.contracts.feed_reader import FeedReader
from app.core.config import settings
from app.core.exceptions import MinifluxAPIError


class MinifluxClient(FeedReader):
    def __init__(self):
        self.base_url = settings.miniflux_url.rstrip("/")
        self.api_key = settings.miniflux_api_key
        self.timeout = settings.miniflux_timeout

    def _get_headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["X-Auth-Token"] = self.api_key
        return headers

    async def health(self) -> Dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(f"{self.base_url}/v1/healthcheck")
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            raise MinifluxAPIError(f"Miniflux health check failed: {e}")

    async def list_feeds(self) -> List[Dict[str, Any]]:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(
                    f"{self.base_url}/v1/feeds", headers=self._get_headers()
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            raise MinifluxAPIError(f"Failed to list feeds: {e}")

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
        params = {
            "limit": limit,
            "offset": offset,
        }
        if feed_id is not None:
            params["feed_id"] = feed_id
        if category_id is not None:
            params["category_id"] = category_id
        if starred is not None:
            params["starred"] = int(starred)
        if read is not None:
            params["status"] = "read" if read else "unread"
        if search:
            params["search"] = search

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(
                    f"{self.base_url}/v1/entries",
                    headers=self._get_headers(),
                    params=params,
                )
                resp.raise_for_status()
                data = resp.json()
                return data.get("entries", [])
        except Exception as e:
            raise MinifluxAPIError(f"Failed to get entries: {e}")

    async def get_entry(self, entry_id: int) -> Dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(
                    f"{self.base_url}/v1/entries/{entry_id}",
                    headers=self._get_headers(),
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            raise MinifluxAPIError(f"Failed to get entry: {e}")

    async def mark_entry_read(self, entry_id: int) -> bool:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.put(
                    f"{self.base_url}/v1/entries",
                    headers=self._get_headers(),
                    json={"entry_ids": [entry_id], "status": "read"},
                )
                resp.raise_for_status()
                return resp.status_code == 204
        except Exception as e:
            raise MinifluxAPIError(f"Failed to mark entry read: {e}")

    async def export_opml(self) -> str:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(
                    f"{self.base_url}/v1/export", headers=self._get_headers()
                )
                resp.raise_for_status()
                return resp.text
        except Exception as e:
            raise MinifluxAPIError(f"Failed to export OPML: {e}")

    async def import_opml(self, opml_content: str) -> Dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    f"{self.base_url}/v1/import",
                    headers={**self._get_headers(), "Content-Type": "text/xml"},
                    content=opml_content,
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            raise MinifluxAPIError(f"Failed to import OPML: {e}")
