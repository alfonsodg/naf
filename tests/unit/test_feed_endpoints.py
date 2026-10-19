"""Feed intake and single-feed management endpoints.

The reader and the validator are stubbed at the port boundary, so these tests
cover routing, body handling, status codes, and error translation.
"""

import json
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core.exceptions import MinifluxAPIError
from app.core.ports.feed_validator import FeedProbe, FeedVerdict
from app.main import app
from app.routers import feeds

client = TestClient(app)

FEEDLY_OPML = """<?xml version="1.0" encoding="UTF-8"?>
<opml version="1.0">
  <body>
    <outline text="Tech">
      <outline type="rss" text="Ars Technica" xmlUrl="https://arstechnica.test/rss"/>
    </outline>
  </body>
</opml>"""


class _ReaderState:
    """Shared state so a stubbed reader can be inspected after a request."""

    def __init__(self) -> None:
        self.created_feeds: list[dict[str, Any]] = []
        self.created_categories: list[str] = []
        self.updated: list[dict[str, Any]] = []
        self.existing: list[str] = []

    def reset(self) -> None:
        """Clear everything between tests."""
        self.created_feeds.clear()
        self.created_categories.clear()
        self.updated.clear()
        self.existing.clear()


state = _ReaderState()


def _probe(url: str) -> FeedProbe:
    """Preset verdicts for the validator stub."""
    if url.endswith("/empty"):
        return FeedProbe(url=url, verdict=FeedVerdict.EMPTY, status_code=200)
    if url.endswith("/throttled"):
        return FeedProbe(url=url, verdict=FeedVerdict.THROTTLED, status_code=403)
    if url.endswith("/dead"):
        return FeedProbe(url=url, verdict=FeedVerdict.HTTP_ERROR, status_code=404)
    return FeedProbe(url=url, verdict=FeedVerdict.ALIVE, status_code=200, item_count=2)


@pytest.fixture(autouse=True)
def stub_collaborators(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace every outbound call for the duration of one test."""
    state.reset()

    async def list_feeds(self: Any) -> list[dict[str, Any]]:
        return [{"id": index + 1, "feed_url": url} for index, url in enumerate(state.existing)]

    async def list_categories(self: Any) -> list[dict[str, Any]]:
        return [{"id": 7, "title": "Tech"}]

    async def create_category(self: Any, title: str) -> dict[str, Any]:
        state.created_categories.append(title)
        return {"id": 99, "title": title}

    async def create_feed(
        self: Any, feed_url: str, *, category_id: int | None = None, title: str | None = None, disabled: bool = False
    ) -> dict[str, Any]:
        state.created_feeds.append(
            {"feed_url": feed_url, "category_id": category_id, "title": title, "disabled": disabled}
        )
        return {"id": 500 + len(state.created_feeds)}

    async def update_feed(self: Any, feed_id: int, **fields: Any) -> dict[str, Any]:
        state.updated.append({"feed_id": feed_id, **fields})
        return {"id": feed_id, **{k: v for k, v in fields.items() if v is not None}}

    async def refresh_feed(self: Any, feed_id: int) -> bool:
        return True

    async def validate(self: Any, url: str) -> FeedProbe:
        return _probe(url)

    async def validate_many(self: Any, urls: list[str], timeout: float | None = None) -> list[FeedProbe]:
        return [_probe(url) for url in urls]

    monkeypatch.setattr(feeds.MinifluxClient, "list_feeds", list_feeds)
    monkeypatch.setattr(feeds.MinifluxClient, "list_categories", list_categories)
    monkeypatch.setattr(feeds.MinifluxClient, "create_category", create_category)
    monkeypatch.setattr(feeds.MinifluxClient, "create_feed", create_feed)
    monkeypatch.setattr(feeds.MinifluxClient, "update_feed", update_feed)
    monkeypatch.setattr(feeds.MinifluxClient, "refresh_feed", refresh_feed)
    monkeypatch.setattr(feeds.HttpFeedValidator, "validate", validate)
    monkeypatch.setattr(feeds.HttpFeedValidator, "validate_many", validate_many)


# --- plain URL list intake ----------------------------------------------------


def test_intake_accepts_a_plain_url_list() -> None:
    """A text body with one URL per line is validated and added."""
    body = "\n".join(["https://a.test/feed", "https://b.test/rss"])
    response = client.post(
        "/api/v1/feeds/intake",
        content=body,
        headers={"Content-Type": "text/plain"},
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["summary"]["received"] == 2
    assert data["summary"]["added"] == 2
    assert [feed["feed_url"] for feed in state.created_feeds] == ["https://a.test/feed", "https://b.test/rss"]


def test_intake_reports_a_dead_feed_without_adding_it() -> None:
    """A 404 feed appears in the report and produces no write."""
    response = client.post(
        "/api/v1/feeds/intake",
        content="https://ok.test/feed\nhttps://gone.test/dead",
        headers={"Content-Type": "text/plain"},
    )

    assert response.status_code == 201
    rows = {row["url"]: row for row in response.json()["data"]["feeds"]}
    assert rows["https://gone.test/dead"]["verdict"] == "http_error"
    assert rows["https://gone.test/dead"]["added"] is False
    assert [feed["feed_url"] for feed in state.created_feeds] == ["https://ok.test/feed"]


def test_intake_adds_a_throttled_feed_disabled() -> None:
    """A bot-blocked feed is added as unverified, never silently dropped."""
    response = client.post(
        "/api/v1/feeds/intake",
        content="https://reddit.test/throttled",
        headers={"Content-Type": "text/plain"},
    )

    assert response.status_code == 201
    row = response.json()["data"]["feeds"][0]
    assert row["disabled"] is True
    assert row["added"] is True
    assert state.created_feeds[0]["disabled"] is True


def test_intake_skips_an_empty_feed() -> None:
    """An empty feed is reported and never written."""
    response = client.post(
        "/api/v1/feeds/intake",
        content="https://quiet.test/empty",
        headers={"Content-Type": "text/plain"},
    )

    assert response.status_code == 201
    assert response.json()["data"]["feeds"][0]["verdict"] == "empty"
    assert state.created_feeds == []


def test_intake_rejects_an_empty_payload() -> None:
    """A body with no URL is a client error, not a silent no-op."""
    response = client.post("/api/v1/feeds/intake", content="\n\n", headers={"Content-Type": "text/plain"})

    assert response.status_code == 422
    assert response.json()["detail"]["error"]["code"] == "FEED_INTAKE_EMPTY"


def test_intake_rejects_a_malformed_opml() -> None:
    """Broken XML is reported with its own code."""
    response = client.post(
        "/api/v1/feeds/intake",
        content="<opml><body>",
        headers={"Content-Type": "text/xml"},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["error"]["code"] == "FEED_INTAKE_INVALID"


# --- OPML intake --------------------------------------------------------------


def test_intake_accepts_a_feedly_export_and_creates_categories() -> None:
    """An OPML body preserves folders as categories."""
    response = client.post(
        "/api/v1/feeds/intake",
        content=FEEDLY_OPML,
        headers={"Content-Type": "text/xml"},
    )

    assert response.status_code == 201
    assert state.created_categories == []
    assert state.created_feeds[0]["category_id"] == 7


def test_intake_creates_an_unknown_category() -> None:
    """A folder with no matching category is created once."""

    async def no_categories(self: Any) -> list[dict[str, Any]]:
        return []

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(feeds.MinifluxClient, "list_categories", no_categories)
        response = client.post(
            "/api/v1/feeds/intake",
            content=FEEDLY_OPML,
            headers={"Content-Type": "text/xml"},
        )

    assert response.status_code == 201
    assert state.created_categories == ["Tech"]
    assert state.created_feeds[0]["category_id"] == 99


# --- single feed endpoints ----------------------------------------------------


def test_create_feed_validates_and_adds() -> None:
    """POST /feeds validates the URL before the reader is asked to store it."""
    response = client.post(
        "/api/v1/feeds",
        json={"feed_url": "https://a.test/feed", "category": "Tech"},
    )

    assert response.status_code == 201
    assert response.json()["data"]["added"] is True
    assert state.created_feeds[0]["category_id"] == 7


def test_create_feed_rejects_a_private_target() -> None:
    """A loopback URL is refused by schema validation, before any request."""
    response = client.post("/api/v1/feeds", json={"feed_url": "http://localhost:8080/feed"})

    assert response.status_code == 422


def test_create_feed_rejects_a_dead_feed() -> None:
    """A feed that fails validation returns a structured refusal."""
    response = client.post("/api/v1/feeds", json={"feed_url": "https://gone.test/dead"})

    assert response.status_code == 422
    assert response.json()["detail"]["error"]["code"] == "FEED_REJECTED"


def test_patch_feed_pauses_it() -> None:
    """PATCH /feeds/{id} can disable a feed."""
    response = client.patch("/api/v1/feeds/12", json={"disabled": True})

    assert response.status_code == 200
    assert state.updated == [{"feed_id": 12, "title": None, "category_id": None, "disabled": True}]


def test_patch_feed_moves_it_to_another_category() -> None:
    """PATCH /feeds/{id} can change the category."""
    response = client.patch("/api/v1/feeds/12", json={"category_id": 7})

    assert response.status_code == 200
    assert state.updated[0]["category_id"] == 7


def test_patch_feed_without_fields_is_rejected() -> None:
    """An empty patch would be a silent no-op, so it is refused."""
    response = client.patch("/api/v1/feeds/12", json={})

    assert response.status_code == 422
    assert response.json()["detail"]["error"]["code"] == "FEED_UPDATE_EMPTY"


def test_refresh_feed_requests_an_update() -> None:
    """POST /feeds/{id}/refresh asks the reader to poll now."""
    response = client.post("/api/v1/feeds/12/refresh")

    assert response.status_code == 200
    assert response.json()["data"] == {"feed_id": 12, "refresh_requested": True}


def test_categories_are_listed() -> None:
    """GET /categories proxies the reader categories."""
    response = client.get("/api/v1/categories")

    assert response.status_code == 200
    assert response.json() == [{"id": 7, "title": "Tech"}]


def test_intake_reader_failure_returns_502() -> None:
    """A reader outage during intake uses the shared error envelope."""

    async def failing(self: Any) -> list[dict[str, Any]]:
        raise MinifluxAPIError("reader down")

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(feeds.MinifluxClient, "list_feeds", failing)
        response = client.post(
            "/api/v1/feeds/intake",
            content="https://a.test/feed",
            headers={"Content-Type": "text/plain"},
        )

    assert response.status_code == 502
    assert response.json()["detail"]["error"]["code"] == "MINIFLUX_UNAVAILABLE"


def test_intake_payload_size_is_enforced() -> None:
    """An oversized payload is refused before it is parsed."""
    from app.core.config import settings

    oversized = "https://a.test/feed\n" * (settings.feed_intake_max_bytes // 10 + 1)
    response = client.post(
        "/api/v1/feeds/intake",
        content=oversized,
        headers={"Content-Type": "text/plain"},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["error"]["code"] == "FEED_INTAKE_TOO_LARGE"


def test_intake_response_is_json_serializable() -> None:
    """The report round-trips through JSON without custom encoders."""
    response = client.post(
        "/api/v1/feeds/intake",
        content="https://a.test/feed",
        headers={"Content-Type": "text/plain"},
    )

    assert json.loads(json.dumps(response.json())) == response.json()


# --- error translation on every new route -------------------------------------


@pytest.mark.parametrize(
    ("method", "route", "payload"),
    [
        ("post", "/api/v1/feeds", {"feed_url": "https://a.test/feed"}),
        ("patch", "/api/v1/feeds/12", {"disabled": True}),
        ("post", "/api/v1/feeds/12/refresh", None),
        ("get", "/api/v1/categories", None),
    ],
)
def test_reader_failure_translates_to_502(method: str, route: str, payload: dict[str, Any] | None) -> None:
    """Every new route uses the shared reader-failure envelope."""

    async def failing(*args: Any, **kwargs: Any) -> Any:
        raise MinifluxAPIError("reader down")

    with pytest.MonkeyPatch.context() as patch:
        for name in ("list_feeds", "list_categories", "create_feed", "update_feed", "refresh_feed"):
            patch.setattr(feeds.MinifluxClient, name, failing)
        response = getattr(client, method)(route, **({"json": payload} if payload else {}))

    assert response.status_code == 502
    assert response.json()["detail"]["error"]["code"] == "MINIFLUX_UNAVAILABLE"


def test_blank_category_is_dropped() -> None:
    """A whitespace-only category is treated as absent, not created."""
    response = client.post(
        "/api/v1/feeds",
        json={"feed_url": "https://a.test/feed", "category": "   "},
    )

    assert response.status_code == 201
    assert state.created_categories == []
