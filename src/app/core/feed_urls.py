"""Candidate feed URL rules shared by parsers, services, and the validator.

A feed URL arriving from a pasted list, an OPML file, or a form field is
untrusted input. Everything here is decided *before* any network request is
made, so a rejected URL never causes an outbound connection.
"""

import ipaddress
from urllib.parse import urlsplit

ALLOWED_SCHEMES = frozenset({"http", "https"})

# Hosts that resolve to the machine running the service or to its metadata
# service. Rejected by name because DNS is not consulted here.
BLOCKED_HOSTNAMES = frozenset(
    {
        "localhost",
        "localhost.localdomain",
        "ip6-localhost",
        "ip6-loopback",
        "metadata",
        "metadata.google.internal",
        "metadata.goog",
        "instance-data",
    }
)

BLOCKED_HOST_SUFFIXES = (".localhost", ".local", ".internal", ".home.arpa")


class FeedURLError(ValueError):
    """A candidate feed URL is malformed or points at a forbidden target."""


def _reject_literal_ip(host: str) -> None:
    """Reject IP literals that are not globally routable."""
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return

    if (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_reserved
        or address.is_multicast
        or address.is_unspecified
    ):
        raise FeedURLError(f"address {host} is not allowed")


def validate_feed_url(url: str) -> str:
    """Return the normalized URL or raise :class:`FeedURLError`.

    The rules are deliberately strict: only ``http``/``https``, a mandatory
    host, no credentials in the authority, and no loopback, link-local, or
    metadata target. Resolution is not performed, so a public hostname that
    resolves internally is caught later, when the redirect target of every hop
    is re-checked by the validator.
    """
    candidate = url.strip()
    if not candidate:
        raise FeedURLError("empty URL")

    try:
        parts = urlsplit(candidate)
    except ValueError as exc:
        raise FeedURLError(f"malformed URL: {exc}") from exc

    if parts.scheme.lower() not in ALLOWED_SCHEMES:
        raise FeedURLError(f"scheme {parts.scheme or '(none)'} is not allowed")

    host = (parts.hostname or "").strip().lower().rstrip(".")
    if not host:
        raise FeedURLError("missing host")
    if parts.username or parts.password:
        raise FeedURLError("credentials in the URL are not allowed")

    if host in BLOCKED_HOSTNAMES or host.endswith(BLOCKED_HOST_SUFFIXES):
        raise FeedURLError(f"host {host} is not allowed")

    _reject_literal_ip(host)

    return candidate
