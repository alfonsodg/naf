"""Live proof for feed intake against a real Miniflux instance.

Run it only against the environment recorded in `REMOTE.md`. It exercises the
whole path: validate a feed that is live, one that answers without entries, and
one that cannot be reached, then add the usable ones and inspect the report and
the reader state.

The exit code is 0 when every expectation holds and 1 otherwise, so the result
can gate a release.

Usage:

    NAF_* environment loaded, then:
    uv run python scripts/feed_intake_proof.py
"""

import asyncio
import json
import sys

from app.adapters.http.feed_validator import HttpFeedValidator
from app.adapters.miniflux.client import MinifluxClient
from app.core.ports.feed_validator import FeedVerdict
from app.services.feed_documents import CandidateFeed
from app.services.feed_intake import FeedIntake

# A live feed, a feed that answers with no entries, and an unreachable host.
# The unreachable one uses the reserved `.invalid` domain, so it can never
# resolve and no real service is contacted by mistake.
LIVE_FEED = "https://blog.google/technology/ai/rss/"
EMPTY_FEED = "https://export.arxiv.org/rss/cs.AI"
DEAD_FEED = "https://dead-feed.invalid/rss"


async def probe_validator() -> dict[str, object]:
    """Prove the validator separates live, empty, and unreachable feeds."""
    validator = HttpFeedValidator()
    live = await validator.validate(LIVE_FEED)
    empty = await validator.validate(EMPTY_FEED)
    dead = await validator.validate(DEAD_FEED)

    return {
        "live": {"verdict": str(live.verdict), "items": live.item_count, "status": live.status_code},
        "empty": {"verdict": str(empty.verdict), "items": empty.item_count, "status": empty.status_code},
        "dead": {"verdict": str(dead.verdict), "status": dead.status_code},
        "live_is_alive": live.verdict is FeedVerdict.ALIVE,
        "empty_is_empty": empty.verdict is FeedVerdict.EMPTY,
        "dead_is_http_error": dead.verdict is FeedVerdict.HTTP_ERROR,
    }


async def probe_ssrf() -> dict[str, object]:
    """Prove a forbidden target is refused without a request being made."""
    validator = HttpFeedValidator()
    blocked = await validator.validate("http://localhost:8080/feed")
    return {"verdict": str(blocked.verdict), "is_blocked": blocked.verdict is FeedVerdict.BLOCKED}


async def probe_intake() -> dict[str, object]:
    """Add the live feed twice and inspect both reports and the reader state."""
    reader = MinifluxClient()
    intake = FeedIntake(reader, HttpFeedValidator())
    candidate = CandidateFeed(url=LIVE_FEED, categories=("prueba",))

    first = await intake.add([candidate])
    second = await intake.add([candidate])
    feeds = await reader.list_feeds()

    return {
        "first_summary": first["summary"],
        "first_row": first["feeds"][0],
        "second_summary": second["summary"],
        "second_is_duplicate": second["feeds"][0]["duplicate"],
        "reader_feed_count": len(feeds),
    }


def main() -> int:
    """Run the live checks and report the outcome."""
    evidence = {
        "validator": asyncio.run(probe_validator()),
        "ssrf": asyncio.run(probe_ssrf()),
        "intake": asyncio.run(probe_intake()),
    }
    print(json.dumps(evidence, indent=2, ensure_ascii=False, default=str))

    validator = evidence["validator"]
    intake = evidence["intake"]
    ok = all(
        (
            validator["live_is_alive"],
            validator["empty_is_empty"],
            validator["dead_is_http_error"],
            evidence["ssrf"]["is_blocked"],
            intake["second_is_duplicate"] is True,
        )
    )
    print("result:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
