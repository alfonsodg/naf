"""Build OPML documents that carry a single feed.

The reader stores an imported feed without fetching it, which is the only way
to keep a subscription whose host refuses automated clients: the creation
endpoint always downloads the feed first, even when the feed is requested
disabled.
"""

from html import escape

MINIFLUX_NAMESPACE = "https://miniflux.app/opml"


def build_feed_opml(url: str, title: str = "", category: str = "", disabled: bool = True) -> str:
    """Return an OPML document carrying one feed.

    The document declares the reader's own namespace so the feed can be
    marked as disabled, and nests the feed under its category so the reader
    resolves the same category the intake would have used.
    """
    attributes = f'type="rss" text={_attribute(title or url)} xmlUrl={_attribute(url)}'
    if disabled:
        attributes += ' miniflux:disabled="true"'

    outline = f"<outline {attributes} />"
    if category:
        outline = f"<outline text={_attribute(category)}>{outline}</outline>"

    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<opml version="2.0" xmlns:miniflux="{MINIFLUX_NAMESPACE}">\n'
        "  <body>\n"
        f"    {outline}\n"
        "  </body>\n"
        "</opml>\n"
    )


def _attribute(value: str) -> str:
    """Return a value quoted and escaped for an XML attribute."""
    return f'"{escape(value, quote=True)}"'
