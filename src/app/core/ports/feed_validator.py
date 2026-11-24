"""Feed validation port. Decides whether a candidate feed is usable."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum


class FeedVerdict(StrEnum):
    """Outcome of probing one candidate feed.

    The values are distinct on purpose: a feed that answers ``200`` with no
    items is not the same as a broken one, and a host that blocks automated
    clients is not the same as a dead feed.
    """

    ALIVE = "alive"
    EMPTY = "empty"
    HTTP_ERROR = "http_error"
    THROTTLED = "throttled"
    TIMEOUT = "timeout"
    BLOCKED = "blocked"
    NOT_PROCESSED = "not_processed"


@dataclass(frozen=True, slots=True)
class FeedProbe:
    """Evidence collected while probing one feed URL.

    ``item_count`` counts only the entries actually parsed, so a caller can tell
    an empty feed from a populated one. ``reason`` is a short, stable
    human-readable explanation; ``status_code`` is ``None`` when no HTTP
    response was received. ``final_url`` is the effective URL after redirects,
    which is what the reader stores, so duplicate detection must use it.
    """

    url: str
    verdict: FeedVerdict
    status_code: int | None = None
    item_count: int = 0
    reason: str = ""
    final_url: str = ""


class FeedValidator(ABC):
    """Probe candidate feeds before they are added to the reader."""

    @abstractmethod
    async def validate(self, url: str) -> FeedProbe:
        """Probe one feed URL and classify the result."""

    @abstractmethod
    async def validate_many(self, urls: list[str], timeout: float | None = None) -> list[FeedProbe]:
        """Probe several URLs with bounded concurrency, preserving input order.

        ``timeout`` caps the time a single probe may take, so a caller can
        keep a whole batch inside its own budget.
        """
