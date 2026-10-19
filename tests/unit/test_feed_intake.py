"""Feed intake: verdict handling and the per-URL report.

The reader and the validator are both stubbed at the port boundary, so these
tests exercise the decision logic only. The parsing of the input document is
covered in `test_intake_parsing.py`.
"""

from typing import Any

import pytest

from app.core.config import settings
from app.core.exceptions import MinifluxAPIError
from app.core.ports.feed_validator import FeedProbe, FeedVerdict
from app.services.feed_intake import (
    CandidateFeed,
    FeedIntake,
)


class StubReader:
    """Reader double recording every write it receives."""

    def __init__(self, *, existing: list[str] | None = None, categories: list[dict[str, Any]] | None = None) -> None:
        self.existing = existing or []
        self.categories = categories or []
        self.created_feeds: list[dict[str, Any]] = []
        self.created_categories: list[str] = []
        self.imported_opml: list[str] = []
        self.fail_create = False
        self.fail_import = False

    async def list_feeds(self) -> list[dict[str, Any]]:
        return [{"id": index + 1, "feed_url": url} for index, url in enumerate(self.existing)]

    async def list_categories(self) -> list[dict[str, Any]]:
        return self.categories

    async def create_category(self, title: str) -> dict[str, Any]:
        self.created_categories.append(title)
        category = {"id": 100 + len(self.created_categories), "title": title}
        self.categories.append(category)
        return category

    async def create_feed(
        self,
        feed_url: str,
        *,
        category_id: int | None = None,
        title: str | None = None,
        disabled: bool = False,
    ) -> dict[str, Any]:
        if self.fail_create:
            raise MinifluxAPIError("reader refused the feed")
        self.created_feeds.append(
            {"feed_url": feed_url, "category_id": category_id, "title": title, "disabled": disabled}
        )
        return {"id": 500 + len(self.created_feeds)}

    async def import_opml(self, opml_content: str) -> dict[str, Any]:
        if self.fail_import:
            raise MinifluxAPIError("reader refused the import")
        self.imported_opml.append(opml_content)
        return {"message": "Feeds imported successfully"}


class StubValidator:
    """Validator double returning preset verdicts keyed by URL."""

    def __init__(self, verdicts: dict[str, FeedVerdict]) -> None:
        self.verdicts = verdicts

    async def validate(self, url: str) -> FeedProbe:
        verdict = self.verdicts.get(url, FeedVerdict.ALIVE)
        return FeedProbe(
            url=url,
            verdict=verdict,
            status_code=200 if verdict in {FeedVerdict.ALIVE, FeedVerdict.EMPTY} else 403,
            item_count=3 if verdict is FeedVerdict.ALIVE else 0,
        )

    async def validate_many(self, urls: list[str], timeout: float | None = None) -> list[FeedProbe]:
        return [await self.validate(url) for url in urls]


def _intake(verdicts: dict[str, FeedVerdict], reader: StubReader | None = None) -> tuple[FeedIntake, StubReader]:
    """Build the service under test with both collaborators stubbed."""
    stub = reader or StubReader()
    return FeedIntake(stub, StubValidator(verdicts)), stub  # type: ignore[arg-type]


# --- intake decisions --------------------------------------------------------


async def test_alive_feed_is_added_enabled() -> None:
    """A feed with entries is added enabled."""
    service, reader = _intake({"https://a.test/feed": FeedVerdict.ALIVE})

    result = await service.add([CandidateFeed(url="https://a.test/feed")])

    assert result["summary"]["added"] == 1
    assert reader.created_feeds == [
        {"feed_url": "https://a.test/feed", "category_id": None, "title": None, "disabled": False}
    ]


async def test_empty_feed_is_reported_and_not_added() -> None:
    """A 200 response with no entries never reaches the reader."""
    service, reader = _intake({"https://a.test/feed": FeedVerdict.EMPTY})

    result = await service.add([CandidateFeed(url="https://a.test/feed")])

    assert reader.created_feeds == []
    row = result["feeds"][0]
    assert row["verdict"] == "empty"
    assert row["added"] is False


@pytest.mark.parametrize("verdict", [FeedVerdict.HTTP_ERROR, FeedVerdict.TIMEOUT, FeedVerdict.BLOCKED])
async def test_unusable_verdicts_are_reported_and_not_added(verdict: FeedVerdict) -> None:
    """Dead, slow, and forbidden URLs are reported without a write."""
    service, reader = _intake({"https://a.test/feed": verdict})

    result = await service.add([CandidateFeed(url="https://a.test/feed")])

    assert reader.created_feeds == []
    assert result["feeds"][0]["verdict"] == str(verdict)
    assert result["feeds"][0]["added"] is False


async def test_throttled_feed_is_added_disabled_and_reported_unverified() -> None:
    """A bot-blocking host must not cost a valid feed, and must not add it enabled."""
    service, reader = _intake({"https://reddit.test/rss": FeedVerdict.THROTTLED})

    result = await service.add([CandidateFeed(url="https://reddit.test/rss")])

    assert reader.created_feeds[0]["disabled"] is True
    row = result["feeds"][0]
    assert row["added"] is True
    assert row["disabled"] is True
    assert "unverified" in row["reason"]


async def test_existing_feed_is_reported_as_duplicate() -> None:
    """An already-present URL is never added twice."""
    reader = StubReader(existing=["https://a.test/feed"])
    service, _ = _intake({"https://a.test/feed": FeedVerdict.ALIVE}, reader)

    result = await service.add([CandidateFeed(url="https://a.test/feed")])

    assert reader.created_feeds == []
    row = result["feeds"][0]
    assert row["duplicate"] is True
    assert row["added"] is False
    assert result["summary"]["already_present"] == 1


async def test_category_is_created_once_and_reused() -> None:
    """A folder shared by several feeds creates a single category."""
    reader = StubReader()
    service, _ = _intake({}, reader)
    candidates = [
        CandidateFeed(url="https://a.test/feed", categories=("Tech",)),
        CandidateFeed(url="https://b.test/feed", categories=("Tech",)),
    ]

    await service.add(candidates)

    assert reader.created_categories == ["Tech"]
    assert {feed["category_id"] for feed in reader.created_feeds} == {101}


async def test_existing_category_is_reused_case_insensitively() -> None:
    """A category that already exists is matched regardless of case."""
    reader = StubReader(categories=[{"id": 7, "title": "tech"}])
    service, _ = _intake({}, reader)

    await service.add([CandidateFeed(url="https://a.test/feed", categories=("Tech",))])

    assert reader.created_categories == []
    assert reader.created_feeds[0]["category_id"] == 7


async def test_reader_refusal_after_a_good_probe_is_reported() -> None:
    """The reader re-fetches the feed; a refusal must not be reported as success."""
    reader = StubReader()
    reader.fail_create = True
    service, _ = _intake({"https://a.test/feed": FeedVerdict.ALIVE}, reader)

    result = await service.add([CandidateFeed(url="https://a.test/feed")])

    row = result["feeds"][0]
    assert row["added"] is False
    assert "reader refused" in row["reason"]
    assert result["summary"]["added"] == 0


async def test_summary_counts_every_verdict() -> None:
    """The summary accounts for every input URL."""
    service, _ = _intake(
        {
            "https://a.test/feed": FeedVerdict.ALIVE,
            "https://b.test/feed": FeedVerdict.EMPTY,
            "https://c.test/feed": FeedVerdict.HTTP_ERROR,
        }
    )

    result = await service.add(
        [
            CandidateFeed(url="https://a.test/feed"),
            CandidateFeed(url="https://b.test/feed"),
            CandidateFeed(url="https://c.test/feed"),
        ]
    )

    summary = result["summary"]
    assert summary["received"] == 3
    assert summary["added"] == 1
    assert summary["rejected"] == 2
    assert summary["by_verdict"] == {"alive": 1, "empty": 1, "http_error": 1}


async def test_report_has_one_row_per_input_url() -> None:
    """Nothing from the input disappears from the report."""
    urls = [f"https://feed{index}.test/rss" for index in range(5)]
    service, _ = _intake({})

    result = await service.add([CandidateFeed(url=url) for url in urls])

    assert [row["url"] for row in result["feeds"]] == urls


async def test_feed_stored_under_its_effective_url_is_a_duplicate() -> None:
    """A redirected feed is already present under the URL the reader stored.

    This is a live finding: Miniflux rewrites a feed to its effective URL, so
    comparing only the submitted address reports a duplicate as a failure.
    """
    reader = StubReader(existing=["https://new.test/feed"])

    class RedirectingValidator(StubValidator):
        async def validate(self, url: str) -> FeedProbe:
            return FeedProbe(
                url=url,
                verdict=FeedVerdict.ALIVE,
                status_code=200,
                item_count=5,
                final_url="https://new.test/feed",
            )

    service = FeedIntake(reader, RedirectingValidator({}))  # type: ignore[arg-type]

    result = await service.add([CandidateFeed(url="https://old.test/feed")])

    row = result["feeds"][0]
    assert row["duplicate"] is True
    assert row["added"] is False
    assert reader.created_feeds == []


async def test_reader_500_on_create_is_reported_as_duplicate_when_present() -> None:
    """A 5xx on creation is re-checked against the reader before being blamed on the feed.

    The reader detects a duplicate by its own effective-URL rewrite and answers
    500. The pre-check cannot see it, so the refusal must be re-verified.
    """
    reader = StubReader()
    reader.fail_create = True

    class RedirectingValidator(StubValidator):
        async def validate(self, url: str) -> FeedProbe:
            return FeedProbe(
                url=url,
                verdict=FeedVerdict.ALIVE,
                status_code=200,
                item_count=5,
                final_url="https://new.test/feed",
            )

    calls = {"count": 0}
    original_list_feeds = reader.list_feeds

    async def list_feeds_after_the_attempt() -> list[dict[str, Any]]:
        """Report the feed only once the refused creation has happened."""
        calls["count"] += 1
        if calls["count"] == 1:
            return []
        return [{"id": 1, "feed_url": "https://new.test/feed"}]

    reader.list_feeds = list_feeds_after_the_attempt  # type: ignore[method-assign]
    service = FeedIntake(reader, RedirectingValidator({}))  # type: ignore[arg-type]

    result = await service.add([CandidateFeed(url="https://old.test/feed")])

    row = result["feeds"][0]
    assert row["duplicate"] is True
    assert "effective URL" in row["reason"]
    assert result["summary"]["already_present"] == 1
    assert original_list_feeds is not None


async def test_a_refused_creation_falls_back_to_the_import() -> None:
    """The reader refuses the fetch, so the feed is kept through the import."""
    reader = StubReader()
    reader.fail_create = True
    service, _ = _intake({"https://reddit.test/rss": FeedVerdict.THROTTLED}, reader)

    result = await service.add([CandidateFeed(url="https://reddit.test/rss")])

    row = result["feeds"][0]
    assert row["added"] is True
    assert row["disabled"] is True
    assert "unverified" in row["reason"]
    assert len(reader.imported_opml) == 1
    assert "https://reddit.test/rss" in reader.imported_opml[0]
    assert 'miniflux:disabled="true"' in reader.imported_opml[0]


async def test_the_import_carries_the_category_of_the_candidate() -> None:
    """The kept feed lands in the category the intake resolved."""
    reader = StubReader()
    reader.fail_create = True
    service, _ = _intake({"https://reddit.test/rss": FeedVerdict.THROTTLED}, reader)

    await service.add([CandidateFeed(url="https://reddit.test/rss", categories=("Tech",))])

    assert '<outline text="Tech">' in reader.imported_opml[0]


async def test_a_refused_creation_and_import_is_reported() -> None:
    """When the reader refuses both paths, the feed is reported, not added."""
    reader = StubReader()
    reader.fail_create = True
    reader.fail_import = True
    service, _ = _intake({"https://reddit.test/rss": FeedVerdict.THROTTLED}, reader)

    result = await service.add([CandidateFeed(url="https://reddit.test/rss")])

    row = result["feeds"][0]
    assert row["added"] is False
    assert "could not fetch it either" in row["reason"]


# --- batch budget ------------------------------------------------------------


async def test_a_batch_over_the_limit_reports_every_candidate(monkeypatch: pytest.MonkeyPatch) -> None:
    """A payload larger than the limit is reported in full, not cut silently."""
    monkeypatch.setattr(settings, "feed_intake_max_batch", 2)
    service, _ = _intake({})
    candidates = [CandidateFeed(url=f"https://a.test/{index}") for index in range(5)]

    result = await service.add(candidates)

    assert result["summary"]["received"] == 5
    assert result["summary"]["processed"] == 2
    assert result["summary"]["not_processed"] == 3
    assert len(result["feeds"]) == 5
    assert [row["processed"] for row in result["feeds"]] == [True, True, False, False, False]
    assert result["feeds"][2]["verdict"] == "not_processed"
    assert result["feeds"][2]["reason"]


async def test_the_overflow_is_never_added_to_the_reader(monkeypatch: pytest.MonkeyPatch) -> None:
    """A candidate the budget left out is not written to the reader."""
    monkeypatch.setattr(settings, "feed_intake_max_batch", 1)
    service, reader = _intake({})
    candidates = [CandidateFeed(url=f"https://a.test/{index}") for index in range(3)]

    await service.add(candidates)

    assert [feed["feed_url"] for feed in reader.created_feeds] == ["https://a.test/0"]


async def test_an_exhausted_time_budget_leaves_the_rest_unprocessed(monkeypatch: pytest.MonkeyPatch) -> None:
    """A batch that runs out of time is reported, never silently cut."""
    monkeypatch.setattr(settings, "feed_intake_time_budget", 0.0)
    service, _ = _intake({})
    candidates = [CandidateFeed(url=f"https://a.test/{index}") for index in range(3)]

    result = await service.add(candidates)

    assert result["summary"]["processed"] == 0
    assert result["summary"]["not_processed"] == 3
    assert all(row["verdict"] == "not_processed" for row in result["feeds"])


async def test_a_batch_inside_the_limit_is_fully_processed(monkeypatch: pytest.MonkeyPatch) -> None:
    """A payload that fits is probed and added as before."""
    monkeypatch.setattr(settings, "feed_intake_max_batch", 50)
    service, reader = _intake({})
    candidates = [CandidateFeed(url=f"https://a.test/{index}") for index in range(3)]

    result = await service.add(candidates)

    assert result["summary"]["processed"] == 3
    assert result["summary"]["not_processed"] == 0
    assert result["summary"]["added"] == 3
    assert len(reader.created_feeds) == 3
