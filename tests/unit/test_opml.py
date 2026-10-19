"""OPML builder: one feed, marked disabled, under its category."""

from defusedxml.ElementTree import fromstring

from app.core.opml import build_feed_opml


def test_the_document_carries_the_feed() -> None:
    """The feed URL and title are in the outline."""
    document = build_feed_opml("https://a.test/feed", "Example")

    assert 'xmlUrl="https://a.test/feed"' in document
    assert 'text="Example"' in document


def test_the_feed_is_marked_disabled() -> None:
    """The reader stores the feed without polling it."""
    document = build_feed_opml("https://a.test/feed")

    assert 'miniflux:disabled="true"' in document
    assert 'xmlns:miniflux="https://miniflux.app/opml"' in document


def test_the_category_nests_the_feed() -> None:
    """The reader resolves the category from the nesting."""
    document = build_feed_opml("https://a.test/feed", "Example", "Tech")

    assert '<outline text="Tech">' in document


def test_the_title_falls_back_to_the_url() -> None:
    """A feed without a title still carries one."""
    document = build_feed_opml("https://a.test/feed")

    assert 'text="https://a.test/feed"' in document


def test_the_document_is_valid_xml() -> None:
    """The reader parses the document as OPML."""
    root = fromstring(build_feed_opml("https://a.test/feed", "Example", "Tech"))

    assert root.tag == "opml"
