import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.adapters.miniflux.client import MinifluxClient
from app.core.exceptions import MinifluxAPIError


@pytest.fixture
def client():
    return MinifluxClient()


@pytest.mark.asyncio
async def test_miniflux_client_implements_contract(client):
    from app.contracts.feed_reader import FeedReader

    assert isinstance(client, FeedReader)


@pytest.mark.asyncio
async def test_get_entries_parses_response(client):
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "entries": [{"id": 1, "title": "Test entry", "url": "https://example.com"}]
    }
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=mock_response)):
        entries = await client.get_entries(limit=10)
        assert len(entries) == 1
        assert entries[0]["title"] == "Test entry"
        assert entries[0]["url"] == "https://example.com"


@pytest.mark.asyncio
async def test_get_entries_error_raises_miniflux_error(client):
    with patch("httpx.AsyncClient.get", side_effect=Exception("connection error")):
        with pytest.raises(MinifluxAPIError):
            await client.get_entries()


@pytest.mark.asyncio
async def test_export_opml_returns_text(client):
    mock_response = MagicMock()
    mock_response.text = "<?xml version='1.0'?><opml/>"
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=mock_response)):
        opml = await client.export_opml()
        assert "<?xml" in opml
