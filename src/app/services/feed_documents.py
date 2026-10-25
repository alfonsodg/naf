"""Reading the feed candidates out of an intake document.

A pasted URL list and an OPML export are two spellings of the same thing: a
list of feed URLs, each with the folders it appeared under. Both are reduced
here, before anything is probed or written.
"""

from dataclasses import dataclass
from typing import Any

from defusedxml.ElementTree import ParseError, fromstring

from app.core.config import settings


@dataclass(frozen=True, slots=True)
class CandidateFeed:
    """One feed URL proposed for addition, with the categories it appeared under."""

    url: str
    title: str = ""
    categories: tuple[str, ...] = ()


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
