"""Reproducible API contract probe against a live Miniflux instance.

Reads every value from the NAF_* environment variables (see
`samples/.env.example`). Run it only against the environment recorded in
`REMOTE.md`, never against production, and never against a locally installed
service.

The exit code is 0 when the reader contract holds and 1 otherwise, so CI can
gate on it.
"""

import asyncio
import json
import sys
from pathlib import Path

from app.adapters.miniflux.client import MinifluxClient

DEBUG_DIR = Path(__file__).resolve().parents[1] / "debug"
REPORT_PATH = DEBUG_DIR / "reader-probe.json"
REQUIRED_ENTRY_FIELDS = ("id", "title", "url", "published_at", "feed")


async def probe() -> dict[str, object]:
    """Exercise the reader contract and collect the evidence."""
    client = MinifluxClient()

    feeds = await client.list_feeds()
    entries = await client.get_entries(limit=5)
    opml = await client.export_opml()
    health = await client.health()

    missing = [field for field in REQUIRED_ENTRY_FIELDS if entries and field not in entries[0]]

    return {
        "feeds": len(feeds),
        "entries_sample": len(entries),
        "provenance_missing_fields": missing,
        "opml_export_valid": "<opml" in opml,
        "health": health.get("status"),
    }


def main() -> int:
    """Run the probe, write the evidence, and report the contract outcome."""
    evidence = asyncio.run(probe())
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(json.dumps(evidence, indent=2))
    print(f"evidence written to {REPORT_PATH}")

    ok = bool(evidence["feeds"]) and not evidence["provenance_missing_fields"] and bool(evidence["opml_export_valid"])
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
