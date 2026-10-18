import pytest
from unittest.mock import AsyncMock

from app.services.collector import Collector


@pytest.fixture
def feed_reader():
    reader = AsyncMock()
    reader.list_feeds.return_value = [
        {
            "id": 1,
            "title": "Feed A",
            "feed_url": "https://a.example/rss",
            "checked_at": "2026-10-18T10:00:00Z",
        },
        {
            "id": 2,
            "title": "Feed B",
            "feed_url": "https://b.example/rss",
            "checked_at": "2026-10-18T10:01:00Z",
        },
    ]
    reader.get_entries.return_value = [
        {
            "id": 10,
            "guid": "guid-10",
            "url": "https://a.example/post-10",
            "title": "Post 10",
            "published_at": "2026-10-18T09:00:00Z",
            "status": "unread",
            "feed": {
                "id": 1,
                "title": "Feed A",
                "feed_url": "https://a.example/rss",
                "site_url": "https://a.example",
            },
        }
    ]
    return reader


@pytest.mark.asyncio
async def test_collect_preserves_provenance(feed_reader):
    result = await Collector(feed_reader).collect(limit=10)
    assert result["total_entries"] == 2
    entry = await Collector(feed_reader).get_entries(limit=10)
    assert entry[0]["entry_id"] == 10
    assert entry[0]["url"] == "https://a.example/post-10"
    assert entry[0]["feed_title"] == "Feed A"
    assert entry[0]["feed_url"] == "https://a.example/rss"


@pytest.mark.asyncio
async def test_one_failing_feed_does_not_block_others(feed_reader):
    async def get_entries(feed_id=None, **kwargs):
        if feed_id == 1:
            raise RuntimeError("boom")
        return [
            {
                "id": 20,
                "guid": "guid-20",
                "url": "https://b.example/post-20",
                "title": "Post 20",
                "published_at": "2026-10-18T08:00:00Z",
                "feed": {
                    "id": 2,
                    "title": "Feed B",
                    "feed_url": "https://b.example/rss",
                },
            }
        ]

    feed_reader.get_entries.side_effect = get_entries
    result = await Collector(feed_reader).collect(limit=10)

    statuses = {f["feed_id"]: f["status"] for f in result["feeds"]}
    assert statuses == {1: "error", 2: "ok"}
    assert result["total_entries"] == 1
    assert len(result["errors"]) == 1


@pytest.mark.asyncio
async def test_since_filter(feed_reader):
    from datetime import datetime, timezone

    result = await Collector(feed_reader).collect(
        limit=10, since=datetime(2026, 10, 19, tzinfo=timezone.utc)
    )
    assert result["total_entries"] == 0
