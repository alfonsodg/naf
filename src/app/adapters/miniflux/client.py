"""Miniflux reader adapter. Access is strictly through the REST API."""

from typing import Any, cast

import httpx

from app.core.config import settings
from app.core.exceptions import MinifluxAPIError
from app.core.ports.feed_reader import FeedReader


class MinifluxClient(FeedReader):
    """Read-only Miniflux API client. Never touches Miniflux tables."""

    def __init__(self) -> None:
        self.base_url = settings.miniflux_url.rstrip("/")
        self.api_key = settings.miniflux_api_key
        self.timeout = settings.miniflux_timeout

    def _headers(self) -> dict[str, str]:
        """Build request headers including the API token."""
        return {"Content-Type": "application/json", "X-Auth-Token": self.api_key}

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        content: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        """Execute one API call, normalizing transport and HTTP errors."""
        request_headers = self._headers()
        if headers:
            request_headers.update(headers)
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.request(
                    method,
                    f"{self.base_url}{path}",
                    params=params,
                    json=json_body,
                    content=content,
                    headers=request_headers,
                )
                response.raise_for_status()
                return response
        except httpx.HTTPStatusError as exc:
            raise MinifluxAPIError(f"Miniflux {path} returned {exc.response.status_code}") from exc
        except httpx.HTTPError as exc:
            raise MinifluxAPIError(f"Miniflux {path} request failed: {exc}") from exc

    async def health(self) -> dict[str, Any]:
        """Return the Miniflux health status."""
        response = await self._request("GET", "/healthcheck")
        return {"status": response.text.strip() or "ok"}

    async def list_feeds(self) -> list[dict[str, Any]]:
        """List every configured feed."""
        response = await self._request("GET", "/v1/feeds")
        return cast(list[dict[str, Any]], response.json())

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
        """List entries with optional filters."""
        entries, _ = await self.get_entries_page(
            feed_id=feed_id,
            limit=limit,
            offset=offset,
            category_id=category_id,
            starred=starred,
            read=read,
            search=search,
        )
        return entries

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
        """List one page of entries and return it with the total count."""
        params: dict[str, Any] = {"limit": limit, "offset": offset}
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

        response = await self._request("GET", "/v1/entries", params=params)
        payload = response.json()
        return cast(list[dict[str, Any]], payload.get("entries", [])), int(payload.get("total", 0))

    async def get_entry(self, entry_id: int) -> dict[str, Any]:
        """Fetch a single entry by id."""
        response = await self._request("GET", f"/v1/entries/{entry_id}")
        return cast(dict[str, Any], response.json())

    async def update_entries_status(self, entry_ids: list[int], status: str) -> bool:
        """Update the read status of one or more entries."""
        response = await self._request(
            "PUT",
            "/v1/entries",
            json_body={"entry_ids": entry_ids, "status": status},
        )
        return response.status_code == httpx.codes.NO_CONTENT

    async def mark_entry_read(self, entry_id: int) -> bool:
        """Mark a single entry as read."""
        return await self.update_entries_status([entry_id], "read")

    async def export_opml(self) -> str:
        """Export all subscriptions as OPML."""
        response = await self._request("GET", "/v1/export")
        return response.text

    async def import_opml(self, opml_content: str) -> dict[str, Any]:
        """Import subscriptions from OPML."""
        response = await self._request(
            "POST",
            "/v1/import",
            content=opml_content,
            headers={"Content-Type": "text/xml"},
        )
        return cast(dict[str, Any], response.json())
