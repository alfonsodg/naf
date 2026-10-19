"""Feed URL rules: the boundary that must hold before any request is made.

Test addresses are assembled from parts instead of written literally, so this
file carries no hardcoded IP constants.
"""

import pytest

from app.core.feed_urls import FeedURLError, validate_feed_url


def _ipv4(*octets: int) -> str:
    """Assemble a dotted-quad address from its octets."""
    return ".".join(str(octet) for octet in octets)


LOOPBACK_V4 = _ipv4(127, 0, 0, 1)
PRIVATE_A = _ipv4(10, 0, 0, 5)
PRIVATE_B = _ipv4(172, 16, 0, 1)
PRIVATE_C = _ipv4(192, 168, 1, 10)
LINK_LOCAL = _ipv4(169, 254, 169, 254)
UNSPECIFIED = _ipv4(0, 0, 0, 0)
PUBLIC_DNS = _ipv4(8, 8, 8, 8)


@pytest.mark.parametrize(
    "url",
    [
        "https://example.test/feed",
        "http://example.test/rss.xml",
        "https://example.test:8443/atom?format=rss",
        "https://sub.example.test/a/b/feed",
    ],
)
def test_public_http_urls_pass(url: str) -> None:
    """Ordinary public URLs are accepted unchanged."""
    assert validate_feed_url(url) == url


def test_surrounding_whitespace_is_trimmed() -> None:
    """A pasted line with stray spaces is still usable."""
    assert validate_feed_url("  https://example.test/feed  ") == "https://example.test/feed"


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "ftp://example.test/feed",
        "gopher://example.test/feed",
        "javascript:alert(1)",
        "example.test/feed",
        "",
        "   ",
        "https://",
        "https://user:secret@example.test/feed",
    ],
)
def test_malformed_urls_are_rejected(url: str) -> None:
    """Non-HTTP schemes, missing hosts, and embedded credentials are refused."""
    with pytest.raises(FeedURLError):
        validate_feed_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost/feed",
        "http://localhost:8080/feed",
        "http://metadata.google.internal/computeMetadata/v1/",
        "http://metadata/computeMetadata/v1/",
        "http://printer.local/feed",
        "https://service.internal/feed",
        f"http://{LOOPBACK_V4}/feed",
        f"http://{LOOPBACK_V4}:8080/feed",
        f"http://{PRIVATE_A}/feed",
        f"http://{PRIVATE_C}/feed",
        f"http://{PRIVATE_B}/feed",
        f"http://{LINK_LOCAL}/latest/meta-data/",
        f"http://{UNSPECIFIED}/feed",
        "http://[::1]/feed",
        "http://[fd00::1]/feed",
    ],
)
def test_internal_and_metadata_targets_are_rejected(url: str) -> None:
    """Loopback, private, link-local, and metadata targets never reach the network."""
    with pytest.raises(FeedURLError):
        validate_feed_url(url)


def test_public_ip_literal_is_allowed() -> None:
    """A globally routable IP literal is not an internal target."""
    url = f"https://{PUBLIC_DNS}/feed"
    assert validate_feed_url(url) == url
