import asyncio
import os

os.environ["NAF_MINIFLUX_URL"] = "http://localhost:8080"

from app.adapters.miniflux.client import MinifluxClient


async def main() -> None:
    client = MinifluxClient()
    # Use basic auth fallback: Miniflux supports X-Auth-Token; for this proof we
    # set the API key by creating one, but basic auth is simpler via httpx patch.
    import httpx

    original = httpx.AsyncClient

    class BasicAuthAsyncClient(original):  # type: ignore[misc, valid-type]
        def __init__(self, *args, **kwargs):
            kwargs.setdefault("auth", httpx.BasicAuth("admin", "test123"))
            super().__init__(*args, **kwargs)

    httpx.AsyncClient = BasicAuthAsyncClient  # type: ignore[misc]

    feeds = await client.list_feeds()
    print(f"OK list_feeds: {len(feeds)} feeds")
    print("  sample:", [f["title"] for f in feeds[:3]])

    entries = await client.get_entries(limit=5)
    print(f"OK get_entries: {len(entries)} entries")
    for e in entries[:3]:
        print(f"  - {e['title'][:60]!r} ({e['published_at']}) via {e['feed']['title']}")

    read_ids = [e["id"] for e in entries[:1]]
    if read_ids:
        ok = await client.mark_entry_read(read_ids[0])
        print(f"OK mark_entry_read: {ok}")

    found = await client.get_entries(limit=5, search="model")
    print(f"OK search 'model': {len(found)} hits")

    opml = await client.export_opml()
    print(f"OK export_opml: {len(opml)} bytes, has <opml>: {'<opml' in opml}")

    # Verify provenance fields are preserved
    if entries:
        e = entries[0]
        required = ["id", "title", "url", "published_at", "feed"]
        missing = [k for k in required if k not in e]
        print(f"OK provenance fields present: {not missing} (missing={missing})")

    health = await client.health()
    print(f"OK health: {health}")


asyncio.run(main())
