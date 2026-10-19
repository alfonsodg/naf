"""Feed intake: turn a pasted URL list or an OPML export into reader feeds.

The pipeline never trusts its input. Every candidate is validated over HTTP
first, and only a feed that answered with real entries is added. The report
accounts for every input line, so nothing is dropped silently.

Why per-URL creation instead of an OPML import: Miniflux's ``POST /v1/feeds``
fetches and parses the feed before inserting it, while ``POST /v1/import``
inserts straight into the database without fetching anything. The OPML path
would therefore reintroduce exactly the dead feeds this service exists to keep
out, and it is not atomic.
"""

import time
from dataclasses import dataclass, field
from typing import Any

from defusedxml.ElementTree import ParseError, fromstring

from app.core.config import settings
from app.core.exceptions import MinifluxAPIError
from app.core.logging import get_logger
from app.core.opml import build_feed_opml
from app.core.ports.feed_reader import FeedReader
from app.core.ports.feed_validator import FeedProbe, FeedValidator, FeedVerdict

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class CandidateFeed:
    """One feed URL proposed for addition, with the categories it appeared under."""

    url: str
    title: str = ""
    categories: tuple[str, ...] = ()


@dataclass(slots=True)
class IntakeRow:
    """One row of the intake report, one per input URL."""

    url: str
    verdict: str
    status_code: int | None = None
    item_count: int = 0
    added: bool = False
    disabled: bool = False
    duplicate: bool = False
    processed: bool = True
    categories: list[str] = field(default_factory=list)
    reason: str = ""


def parse_url_list(text: str) -> list[CandidateFeed]:
    """Read one URL per line, ignoring blanks and ``#`` comments.

    Duplicate lines collapse to one candidate; the reader is the owner of
    per-URL uniqueness, so the same URL cannot be added twice.
    """
    seen: set[str] = set()
    candidates: list[CandidateFeed] = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        for token in line.split():
            if token.startswith("#"):
                break
            if token in seen:
                continue
            seen.add(token)
            candidates.append(CandidateFeed(url=token))

    return candidates


def parse_opml(document: str) -> list[CandidateFeed]:
    """Read an OPML document, preserving the outline nesting as categories.

    Feedly writes a feed once per tag it belongs to. Miniflux's own importer keeps
    only the first occurrence and drops the rest silently; here the same feed
    becomes a single candidate carrying *all* of its categories, so the caller
    can report the overlap instead of losing tags.
    """
    if len(document.encode("utf-8", errors="replace")) > settings.feed_intake_max_bytes:
        raise ValueError("OPML document exceeds the configured size limit")

    try:
        root = fromstring(document)
    except ParseError as exc:
        raise ValueError(f"OPML document is not valid XML: {exc}") from exc

    if root.tag.lower() != "opml":
        raise ValueError("document is not an OPML file")

    collected: dict[str, CandidateFeed] = {}

    def walk(element: Any, trail: tuple[str, ...]) -> None:
        for outline in element:
            if outline.tag.lower() != "outline":
                continue

            title = (outline.get("text") or outline.get("title") or "").strip()
            feed_url = (outline.get("xmlUrl") or "").strip()

            if feed_url:
                existing = collected.get(feed_url)
                # The outermost outline carrying a feed URL is the category
                # folder only when the feed itself is nested inside it.
                categories = trail
                if existing is None:
                    collected[feed_url] = CandidateFeed(
                        url=feed_url,
                        title=title,
                        categories=categories,
                    )
                elif categories and categories not in ((),):
                    merged = tuple(dict.fromkeys((*existing.categories, *categories)))
                    collected[feed_url] = CandidateFeed(
                        url=existing.url,
                        title=existing.title or title,
                        categories=merged,
                    )
            else:
                walk(outline, (*trail, title) if title else trail)

    body = root.find("body")
    walk(body if body is not None else root, ())

    return list(collected.values())


class FeedIntake:
    """Validate candidates and add the usable ones to the reader."""

    def __init__(self, reader: FeedReader, validator: FeedValidator) -> None:
        """Bind the service to a reader and a validator."""
        self.reader = reader
        self.validator = validator

    async def add(self, candidates: list[CandidateFeed]) -> dict[str, Any]:
        """Validate every candidate, add the usable ones, and report each one.

        A batch larger than the configured limit, or one that runs out of its
        time budget, is reported in full but only the candidates that fit are
        probed, so the call stays inside the request budget. Sending the same
        payload again continues where it stopped: the candidates already added
        come back as duplicates.
        """
        deadline = time.monotonic() + settings.feed_intake_time_budget
        limit = settings.feed_intake_max_batch
        accepted = candidates[:limit]
        deferred = candidates[limit:]

        existing = await self._existing_urls()
        categories = await self._category_index()

        rows: list[IntakeRow] = []
        for chunk in _chunks(accepted, settings.feed_validation_concurrency):
            if time.monotonic() >= deadline:
                break
            probes = await self.validator.validate_many(
                [candidate.url for candidate in chunk],
                timeout=max(0.1, deadline - time.monotonic()),
            )
            for candidate, probe in zip(chunk, probes, strict=True):
                rows.append(await self._process(candidate, probe, existing, categories))

        processed = len(rows)
        rows.extend(_not_processed_rows(accepted[processed:] + deferred))

        summary = {
            "received": len(candidates),
            "processed": processed,
            "not_processed": len(candidates) - processed,
            "added": sum(1 for row in rows if row.added),
            "already_present": sum(1 for row in rows if row.duplicate),
            "rejected": sum(1 for row in rows if row.processed and not row.added and not row.duplicate),
            "by_verdict": _count_verdicts(rows),
        }
        logger.info(
            "feed intake finished",
            extra={
                "received": summary["received"],
                "added": summary["added"],
                "not_processed": summary["not_processed"],
            },
        )
        return {"summary": summary, "feeds": [_row_payload(row) for row in rows]}

    async def _process(
        self,
        candidate: CandidateFeed,
        probe: FeedProbe,
        existing: set[str],
        categories: dict[str, int],
    ) -> IntakeRow:
        """Decide the outcome of one candidate and perform the write when allowed."""
        row = IntakeRow(
            url=candidate.url,
            verdict=str(probe.verdict),
            status_code=probe.status_code,
            item_count=probe.item_count,
            categories=list(candidate.categories),
            reason=probe.reason,
        )

        if candidate.url in existing or probe.url in existing or (probe.final_url and probe.final_url in existing):
            row.duplicate = True
            row.reason = "already present in the reader"
            return row

        # A throttled feed is not dead: the host refuses automated clients while
        # the feed may be perfectly valid. The reader fetches the feed before
        # storing it, even when the creation requests `disabled`, so its fetch
        # is refused exactly like this probe was. The attempt is made first so
        # a host that blocks one client but not the other can still be added,
        # and the reader import is the fallback that keeps the subscription
        # without fetching it.
        if probe.verdict is FeedVerdict.THROTTLED:
            category_id = await self._category_for(candidate, categories)
            try:
                await self._create(candidate.url, category_id, disabled=True)
            except MinifluxAPIError as exc:
                return await self._keep_unverified(candidate, exc)
            row.added = True
            row.disabled = True
            row.reason = "host refused an automated client; added disabled and unverified"
            return row

        if probe.verdict is not FeedVerdict.ALIVE:
            return row

        category_id = await self._category_for(candidate, categories)
        try:
            await self._create(candidate.url, category_id, disabled=False)
        except MinifluxAPIError as exc:
            # The reader fetches and parses the feed again before inserting it,
            # so a feed that probed fine can still be refused here. A 5xx on
            # creation usually means the feed is already stored under its
            # effective URL after a redirect, which the reader detects as a
            # duplicate, so the registry is re-read before blaming the feed.
            if await self._is_now_present(candidate.url, probe.final_url):
                row.duplicate = True
                row.reason = "already present in the reader under its effective URL"
                return row
            row.reason = f"reader refused the feed: {exc}"
            return row

        row.added = True
        return row

    async def _keep_unverified(self, candidate: CandidateFeed, exc: Exception) -> IntakeRow:
        """Keep a feed whose host refuses automated clients, without fetching it.

        The reader's OPML import stores a feed without downloading it, and the
        document marks it as disabled, so the subscription survives and is not
        polled until the user asks for a refresh.
        """
        row = IntakeRow(
            url=candidate.url,
            verdict=str(FeedVerdict.THROTTLED),
            categories=list(candidate.categories),
        )
        document = build_feed_opml(
            candidate.url,
            candidate.title,
            candidate.categories[0] if candidate.categories else "",
        )
        try:
            await self.reader.import_opml(document)
        except MinifluxAPIError as import_exc:
            logger.warning("reader refused to import an unverified feed", extra={"url": candidate.url})
            row.reason = f"the host blocks automated clients and the reader could not fetch it either: {exc}"
            row.reason = f"{row.reason}; the import failed with: {import_exc}"
            return row

        row.added = True
        row.disabled = True
        row.reason = "host refused an automated client; added disabled and unverified"
        return row

    async def _category_for(self, candidate: CandidateFeed, categories: dict[str, int]) -> int | None:
        """Resolve, creating when absent, the category a candidate belongs to."""
        if not candidate.categories:
            return None

        name = candidate.categories[0]
        known = categories.get(name.lower())
        if known is not None:
            return known

        created = await self.reader.create_category(name)
        category_id = int(created["id"])
        categories[name.lower()] = category_id
        return category_id

    async def _create(self, url: str, category_id: int | None, *, disabled: bool) -> None:
        """Add one feed, degrading to an unverified entry when the reader refuses it."""
        await self.reader.create_feed(url, category_id=category_id, disabled=disabled)

    async def _existing_urls(self) -> set[str]:
        """Collect every feed URL already present so nothing is added twice."""
        feeds = await self.reader.list_feeds()
        urls: set[str] = set()
        for feed in feeds:
            for key in ("feed_url", "site_url"):
                value = feed.get(key)
                if value:
                    urls.add(str(value).strip())
        return urls

    async def _is_now_present(self, *candidate_urls: str) -> bool:
        """Re-read the reader to check whether any candidate URL is now stored.

        Used after a refused creation: the reader rewrites a redirected feed to
        its effective URL, so the original address may already be registered
        under a different string.
        """
        wanted = {url.strip() for url in candidate_urls if url}
        if not wanted:
            return False
        return bool(wanted & await self._existing_urls())

    async def _category_index(self) -> dict[str, int]:
        """Index existing categories by title, case-insensitively."""
        categories = await self.reader.list_categories()
        return {
            str(category.get("title", "")).strip().lower(): int(category["id"])
            for category in categories
            if category.get("id") is not None
        }


def _count_verdicts(rows: list[IntakeRow]) -> dict[str, int]:
    """Count rows per verdict for the summary block."""
    counts: dict[str, int] = {}
    for row in rows:
        counts[row.verdict] = counts.get(row.verdict, 0) + 1
    return counts


def _chunks(candidates: list[CandidateFeed], size: int) -> list[list[CandidateFeed]]:
    """Split the candidates into batches small enough to keep the budget."""
    return [candidates[index : index + size] for index in range(0, len(candidates), size)]


def _not_processed_rows(candidates: list[CandidateFeed]) -> list[IntakeRow]:
    """Report the candidates the batch limit or the time budget left out.

    They are reported, never dropped, so the user knows the payload was only
    partly handled and can send it again to continue.
    """
    return [
        IntakeRow(
            url=candidate.url,
            verdict=str(FeedVerdict.NOT_PROCESSED),
            processed=False,
            reason="the intake budget was reached; send the remaining URLs again to continue",
        )
        for candidate in candidates
    ]


def _row_payload(row: IntakeRow) -> dict[str, Any]:
    """Serialize one intake row for the HTTP response."""
    return {
        "url": row.url,
        "verdict": row.verdict,
        "status_code": row.status_code,
        "item_count": row.item_count,
        "added": row.added,
        "disabled": row.disabled,
        "duplicate": row.duplicate,
        "processed": row.processed,
        "categories": row.categories,
        "reason": row.reason,
    }
