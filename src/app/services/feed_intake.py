"""Feed intake: turn a pasted URL list or an OPML export into reader feeds.

The pipeline never trusts its input. Every candidate is validated over HTTP
first, and only a feed that answered with real entries is added. The report
accounts for every input line, so nothing is dropped silently. Reading the
document itself lives in :mod:`app.services.feed_documents`, and the report in
:mod:`app.services.feed_intake_report`.

Why per-URL creation instead of an OPML import: Miniflux's ``POST /v1/feeds``
fetches and parses the feed before inserting it, while ``POST /v1/import``
inserts straight into the database without fetching anything. The OPML path
would therefore reintroduce exactly the dead feeds this service exists to keep
out, and it is not atomic.
"""

import time
from typing import Any

from app.core.config import settings
from app.core.exceptions import MinifluxAPIError
from app.core.logging import get_logger
from app.core.opml import build_feed_opml
from app.core.ports.feed_reader import FeedReader
from app.core.ports.feed_validator import FeedProbe, FeedValidator, FeedVerdict
from app.services.feed_documents import CandidateFeed
from app.services.feed_folders import FolderRecorder
from app.services.feed_intake_report import IntakeRow, count_verdicts, not_processed_rows, row_payload

logger = get_logger(__name__)


class FeedIntake:
    """Validate candidates and add the usable ones to the reader."""

    def __init__(self, reader: FeedReader, validator: FeedValidator, folders: FolderRecorder | None = None) -> None:
        """Bind the service to a reader and a validator."""
        self.reader = reader
        self.validator = validator
        self.folders = folders

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
        index = 0
        while index < len(accepted):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            chunk = accepted[index : index + _chunk_size()]
            probes = await self.validator.validate_many(
                [candidate.url for candidate in chunk],
                timeout=max(0.1, min(settings.feed_validation_timeout, remaining / _attempts())),
            )
            for candidate, probe in zip(chunk, probes, strict=True):
                rows.append(await self._process(candidate, probe, existing, categories))
            index += len(chunk)

        processed = len(rows)
        rows.extend(not_processed_rows(accepted[processed:] + deferred))

        summary = {
            "received": len(candidates),
            "processed": processed,
            "not_processed": len(candidates) - processed,
            "added": sum(1 for row in rows if row.added),
            "already_present": sum(1 for row in rows if row.duplicate),
            "rejected": sum(1 for row in rows if row.processed and not row.added and not row.duplicate),
            "by_verdict": count_verdicts(rows),
        }
        logger.info(
            "feed intake finished",
            extra={
                "received": summary["received"],
                "added": summary["added"],
                "not_processed": summary["not_processed"],
            },
        )
        return {"summary": summary, "feeds": [row_payload(row) for row in rows]}

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
            category_id, applied = await self._category_for(candidate, categories)
            row.applied_category = applied
            row.reported_categories = list(candidate.categories[1:])
            try:
                await self._create(candidate.url, category_id, disabled=True)
            except MinifluxAPIError as exc:
                return await self._keep_unverified(candidate, row, exc)
            row.added = True
            row.disabled = True
            row.reason = "host refused an automated client; added disabled and unverified"
            self._record_folders(candidate.url, row.reported_categories)
            return row

        if probe.verdict is not FeedVerdict.ALIVE:
            return row

        category_id, applied = await self._category_for(candidate, categories)
        row.applied_category = applied
        row.reported_categories = list(candidate.categories[1:])
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
        self._record_folders(candidate.url, row.reported_categories)
        return row

    def _record_folders(self, feed_url: str, folders: list[str]) -> None:
        """Keep the folders that were found but could not be applied."""
        if not folders or self.folders is None:
            return
        try:
            self.folders.record(feed_url, folders)
        except Exception as exc:
            # The folders are a convenience; losing them must never cost the
            # subscription that was just added.
            logger.warning("could not store the reported folders", extra={"url": feed_url, "error": type(exc).__name__})

    async def _keep_unverified(self, candidate: CandidateFeed, row: IntakeRow, exc: Exception) -> IntakeRow:
        """Keep a feed whose host refuses automated clients, without fetching it.

        The reader's OPML import stores a feed without downloading it, and the
        document marks it as disabled, so the subscription survives and is not
        polled until the user asks for a refresh.
        """
        document = build_feed_opml(
            candidate.url,
            candidate.title,
            row.applied_category,
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
        self._record_folders(candidate.url, row.reported_categories)
        return row

    async def _category_for(self, candidate: CandidateFeed, categories: dict[str, int]) -> tuple[int | None, str]:
        """Resolve, creating when absent, the category a candidate belongs to.

        Returns the category identifier and its title, so the report can say
        which category was applied.
        """
        if not candidate.categories:
            return None, ""

        name = candidate.categories[0]
        known = categories.get(name.lower())
        if known is not None:
            return known, name

        created = await self.reader.create_category(name)
        category_id = int(created["id"])
        categories[name.lower()] = category_id
        return category_id, name

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


def _attempts() -> int:
    """Return how many requests one probe may make, including its retries."""
    return 1 + settings.feed_validation_max_retries


def _chunk_size() -> int:
    """Return how many candidates one round of the budget may probe.

    One probe may spend its timeout once per attempt, and the per-host limit
    turns a chunk into ceil(size / per_host) rounds. Sizing the chunk as
    ``per_host x attempts`` keeps that product at or under the remaining
    budget, whatever the shape of the input.
    """
    return max(1, settings.feed_validation_per_host_concurrency * _attempts())
