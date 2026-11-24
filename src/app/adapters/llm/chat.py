"""Minimal OpenAI-compatible chat client shared by the LLM adapters.

One client owns one ``httpx.AsyncClient`` so the adapter reuses the connection.
Transport failures, status failures, and unexpected payloads become ``NafError``:
callers translate them into their own domain error without leaking the API key
or the provider's raw body.
"""

from typing import Any, cast

import httpx

from app.core.exceptions import NafError

CHAT_PATH = "chat/completions"
TEMPERATURE = 0.0


class ChatClient:
    """Ask an OpenAI-compatible endpoint for one JSON completion."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout: float = 120.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        """Bind the client to one provider configuration."""
        self._api_key = api_key
        self._model = model
        self._client = httpx.AsyncClient(base_url=base_url, timeout=timeout, transport=transport)

    async def complete(self, messages: list[dict[str, str]], *, max_tokens: int | None = None) -> str:
        """Return the text of one completion, requesting a JSON object."""
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": TEMPERATURE,
            "response_format": {"type": "json_object"},
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        response = await self._post(payload)
        if response.status_code == 400:
            # Several OpenAI-compatible providers reject response_format outright.
            payload.pop("response_format", None)
            response = await self._post(payload)
        if response.status_code >= 400:
            raise NafError(f"the chat provider answered {response.status_code}")

        try:
            data = cast(dict[str, Any], response.json())
            content = data["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise NafError("the chat provider returned an unexpected response") from exc
        if not isinstance(content, str) or not content.strip():
            raise NafError("the chat provider returned an empty completion")
        return content

    async def _post(self, payload: dict[str, Any]) -> httpx.Response:
        """Send one completion request, normalising transport failures."""
        headers = {"Authorization": f"Bearer {self._api_key}"}
        try:
            return await self._client.post(CHAT_PATH, json=payload, headers=headers)
        except httpx.HTTPError as exc:
            raise NafError(f"the chat provider could not be reached: {exc}") from exc
