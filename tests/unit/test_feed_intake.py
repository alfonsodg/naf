"""Feed intake: parsing, verdict handling, and the per-URL report.

The reader and the validator are both stubbed at the port boundary, so these
tests exercise the decision logic only.
"""

from typing import Any

import pytest

from app.core.exceptions import MinifluxAPIError
from app.core.ports.feed_validator import FeedProbe, FeedVerdict
from app.services.feed_intake import (
    CandidateFeed,
    FeedIntake,
    parse_opml,
    parse_url_list,
)

FEEDLY_OPML = """<?xml version="1.0" encoding="UTF-8"?>
<opml version="1.0">
  <head><title>Subscriptions in feedly Cloud</title></head>
  <body>
    <outline text="Tech" title="Tech">
      <outline type="rss" text="Ars Technica" xmlUrl="https://arstechnica.test/rss" htmlUrl="https://arstechnica.test"/>
      <outline type="rss" text="The Verge" xmlUrl="https://verge.test/rss" htmlUrl="https://verge.test"/>
    </outline>
    <outline text="AI" title="AI">
      <outline type="rss" text="Ars Technica" xmlUrl="https://arstechnica.test/rss" htmlUrl="https://arstechnica.test"/>
      <outline type="rss" text="DeepMind" xmlUrl="https://deepmind.test/blog/rss"/>
    </outline>
    <outline type="rss" text="Loose feed" xmlUrl="https://loose.test/feed"/>
  </body>
</opml>"""


class StubReader:
    """Reader double recording every write it receives."""

    def __init__(self, *, existing: list[str] | None = None, categories: list[dict[str, Any]] | None = None) -> None:
        self.existing = existing or []
        self.categories = categories or []
        self.created_feeds: list[dict[str, Any]] = []
        self.created_categories: list[str] = []
        self.fail_create = False

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

    async def validate_many(self, urls: list[str]) -> list[FeedProbe]:
        return [await self.validate(url) for url in urls]


def _intake(verdicts: dict[str, FeedVerdict], reader: StubReader | None = None) -> tuple[FeedIntake, StubReader]:
    """Build the service under test with both collaborators stubbed."""
    stub = reader or StubReader()
    return FeedIntake(stub, StubValidator(verdicts)), stub  # type: ignore[arg-type]


# --- parsing -----------------------------------------------------------------


def test_url_list_ignores_blanks_and_comments() -> None:
    """A pasted list tolerates blank lines and comments."""
    text = """
    # my technical feeds
    https://a.test/feed

    https://b.test/rss
    """
    candidates = parse_url_list(text)

    assert [candidate.url for candidate in candidates] == ["https://a.test/feed", "https://b.test/rss"]


def test_url_list_deduplicates() -> None:
    """The same URL twice collapses to one candidate."""
    candidates = parse_url_list("https://a.test/feed\nhttps://a.test/feed\n")

    assert len(candidates) == 1


def test_url_list_allows_trailing_comment_on_a_line() -> None:
    """An inline comment after a URL is ignored."""
    candidates = parse_url_list("https://a.test/feed  # technology\n")

    assert [candidate.url for candidate in candidates] == ["https://a.test/feed"]


def test_opml_preserves_category_nesting() -> None:
    """Folder outlines become the categories of their feeds."""
    candidates = {candidate.url: candidate for candidate in parse_opml(FEEDLY_OPML)}

    assert candidates["https://verge.test/rss"].categories == ("Tech",)
    assert candidates["https://deepmind.test/blog/rss"].categories == ("AI",)


def test_opml_feed_under_several_tags_keeps_all_of_them() -> None:
    """Miniflux keeps only the first tag; here the overlap is preserved and reported."""
    candidates = {candidate.url: candidate for candidate in parse_opml(FEEDLY_OPML)}

    assert candidates["https://arstechnica.test/rss"].categories == ("Tech", "AI")


def test_opml_feed_outside_a_folder_has_no_category() -> None:
    """A top-level subscription is imported without a category."""
    candidates = {candidate.url: candidate for candidate in parse_opml(FEEDLY_OPML)}

    assert candidates["https://loose.test/feed"].categories == ()


def test_opml_counts_each_feed_once() -> None:
    """Repeated xmlUrl values do not produce duplicate candidates."""
    candidates = parse_opml(FEEDLY_OPML)

    assert len(candidates) == len({candidate.url for candidate in candidates})


def test_opml_rejects_a_non_opml_document() -> None:
    """An unrelated XML document is refused, not partially parsed."""
    with pytest.raises(ValueError, match="not an OPML"):
        parse_opml("<?xml version='1.0'?><rss><channel/></rss>")


def test_opml_rejects_malformed_xml() -> None:
    """Broken XML raises a clear error instead of a parser traceback."""
    with pytest.raises(ValueError, match="not valid XML"):
        parse_opml("<opml><body>")


def test_opml_rejects_an_entity_expansion_payload() -> None:
    """Billion-laughs style entities are refused by defusedxml."""
    payload = """<?xml version="1.0"?>
    <!DOCTYPE opml [<!ENTITY a "aaaaaaaaaa"><!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;">]>
    <opml version="2.0"><body><outline text="&b;" xmlUrl="https://x.test/feed"/></body></opml>"""

    with pytest.raises(ValueError):
        parse_opml(payload)


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


async def test_reader_refusal_of_an_unverified_feed_is_reported() -> None:
    """The disabled write can be refused too; that must not look like success."""
    reader = StubReader()
    reader.fail_create = True
    service, _ = _intake({"https://reddit.test/rss": FeedVerdict.THROTTLED}, reader)

    result = await service.add([CandidateFeed(url="https://reddit.test/rss")])

    row = result["feeds"][0]
    assert row["added"] is False
    assert "could not fetch it either" in row["reason"]


def test_opml_action_outlines_are_ignored() -> None:
    """Non-outline elements inside body are skipped rather than crashing."""
    document = """<?xml version="1.0"?>
    <opml version="2.0"><body>
      <note>ignored</note>
      <outline text="Tech"><outline type="rss" text="A" xmlUrl="https://a.test/feed"/></outline>
    </body></opml>"""

    candidates = parse_opml(document)

    assert [(candidate.url, candidate.categories) for candidate in candidates] == [("https://a.test/feed", ("Tech",))]


def test_opml_outline_without_a_name_keeps_the_parent_category() -> None:
    """An unnamed nested folder does not erase the category above it."""
    document = """<?xml version="1.0"?>
    <opml version="2.0"><body>
      <outline text="Tech">
        <outline>
          <outline type="rss" text="A" xmlUrl="https://a.test/feed"/>
        </outline>
      </outline>
    </body></opml>"""

    candidates = parse_opml(document)

    assert candidates[0].categories == ("Tech",)
