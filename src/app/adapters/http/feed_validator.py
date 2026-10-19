"""HTTP feed validator. Probes a candidate feed without trusting its source.

A feed URL taken from a pasted list or an OPML export is untrusted. This adapter
decides whether it is usable by fetching it directly, so a catalogue's own
"active" flag never decides anything.
"""

import asyncio
import re
import socket
from urllib.parse import SplitResult, urlsplit, urlunsplit

import httpx

from app.core.config import settings
from app.core.feed_urls import FeedURLError, validate_feed_url
from app.core.logging import get_logger
from app.core.ports.feed_validator import FeedProbe, FeedValidator, FeedVerdict
from app.core.resolver import resolve_host_addresses, select_public_address

logger = get_logger(__name__)

# Any of these in the body means the document carries at least one entry, which
# is what separates a working feed from a live but empty one.
_ITEM_PATTERN = re.compile(r"<(item|entry)[\s>]", re.IGNORECASE)

# Status codes that mean "this host refuses automated clients", not "this feed
# is gone". Reddit and several CDNs answer these to non-browser clients while
# serving the very same feed to a browser.
_THROTTLE_CODES = frozenset({401, 403, 405, 406, 409, 418, 429})

_USER_AGENT = "naf-feed-validator/0.1 (+https://github.com/alfonsodg/naf)"


class HttpFeedValidator(FeedValidator):
    """Validate feeds over HTTP with bounded concurrency and re-checked hops."""

    def __init__(self) -> None:
        self.timeout = settings.feed_validation_timeout
        self.concurrency = settings.feed_validation_concurrency
        self.max_redirects = settings.feed_validation_max_redirects
        self.max_bytes = settings.feed_intake_max_bytes

    async def validate_many(self, urls: list[str]) -> list[FeedProbe]:
        """Probe every URL concurrently, preserving the input order."""
        if not urls:
            return []

        semaphore = asyncio.Semaphore(self.concurrency)

        async def guarded(url: str) -> FeedProbe:
            async with semaphore:
                return await self.validate(url)

        return list(await asyncio.gather(*(guarded(url) for url in urls)))

    async def validate(self, url: str) -> FeedProbe:
        """Probe one URL and classify what came back."""
        try:
            normalized = validate_feed_url(url)
        except FeedURLError as exc:
            return FeedProbe(url=url, verdict=FeedVerdict.BLOCKED, reason=str(exc))

        try:
            status_code, body, final_url = await self._fetch(normalized)
        except FeedURLError as exc:
            # A redirect tried to reach a forbidden target. Refuse the whole
            # probe instead of completing the hop.
            return FeedProbe(url=normalized, verdict=FeedVerdict.BLOCKED, reason=str(exc))
        except socket.gaierror as exc:
            # The name does not resolve, so the host cannot be reached. That is
            # an unreachable feed, not a forbidden target.
            return FeedProbe(url=normalized, verdict=FeedVerdict.HTTP_ERROR, reason=f"name resolution failed: {exc}")
        except httpx.TimeoutException:
            return FeedProbe(url=normalized, verdict=FeedVerdict.TIMEOUT, reason="no response in time")
        except httpx.HTTPError as exc:
            return FeedProbe(
                url=normalized,
                verdict=FeedVerdict.HTTP_ERROR,
                reason=f"{type(exc).__name__}: {exc}",
            )

        if status_code >= 400:
            verdict = FeedVerdict.THROTTLED if status_code in _THROTTLE_CODES else FeedVerdict.HTTP_ERROR
            return FeedProbe(
                url=normalized,
                verdict=verdict,
                status_code=status_code,
                reason=f"HTTP {status_code}",
                final_url=final_url,
            )

        if not _looks_like_feed(body):
            return FeedProbe(
                url=normalized,
                verdict=FeedVerdict.HTTP_ERROR,
                status_code=status_code,
                reason="response is not an RSS or Atom document",
                final_url=final_url,
            )

        items = len(_ITEM_PATTERN.findall(body))
        if items == 0:
            return FeedProbe(
                url=normalized,
                verdict=FeedVerdict.EMPTY,
                status_code=status_code,
                reason="document parsed but carries no entries",
                final_url=final_url,
            )

        return FeedProbe(
            url=normalized,
            verdict=FeedVerdict.ALIVE,
            status_code=status_code,
            item_count=items,
            reason=f"{items} entries",
            final_url=final_url,
        )

    async def _fetch(self, url: str) -> tuple[int, str, str]:
        """Fetch a feed, re-validating every redirect target before following it.

        httpx follows redirects transparently, which would let a public URL
        redirect into a private address. Redirects are therefore followed
        manually so each hop passes :func:`validate_feed_url` first, and each
        hop is resolved and pinned so the socket reaches the address that was
        actually validated.

        Returns the status code, the decoded body, and the effective URL. The
        effective URL matters because the reader stores *it* as the feed
        address, so duplicate detection has to compare the same value.
        """
        async with httpx.AsyncClient(
            timeout=self.timeout,
            follow_redirects=False,
            headers={
                "User-Agent": _USER_AGENT,
                "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml;q=0.9, */*;q=0.5",
            },
        ) as client:
            current = url
            for _hop in range(self.max_redirects + 1):
                response = await client.send(await self._build_request(client, current))
                if not response.is_redirect:
                    return response.status_code, _read_capped(response, self.max_bytes), current

                location = response.headers.get("location", "")
                if not location:
                    return response.status_code, "", current
                current = validate_feed_url(str(httpx.URL(current).join(location)))

            raise httpx.TooManyRedirects(
                f"more than {self.max_redirects} redirects",
                request=httpx.Request("GET", current),
            )

    async def _build_request(self, client: httpx.AsyncClient, url: str) -> httpx.Request:
        """Resolve the target and pin the connection to the validated address.

        The request keeps the original hostname in the ``Host`` header and in
        the TLS server name, so certificate verification and virtual hosting
        still work, while the socket only ever reaches an address that passed
        the public-address policy.
        """
        parts = urlsplit(url)
        host = parts.hostname or ""
        port = parts.port or (443 if parts.scheme == "https" else 80)

        addresses = await resolve_host_addresses(host, port)
        address = select_public_address(host, addresses)

        return client.build_request(
            "GET",
            _pinned_url(url, address),
            headers={"Host": _authority(parts)},
            extensions={"sni_hostname": host},
        )


def _authority(parts: SplitResult) -> str:
    """Return the authority as the caller wrote it, without the credentials."""
    host = parts.hostname or ""
    if ":" in host:
        host = f"[{host}]"
    return f"{host}:{parts.port}" if parts.port else host


def _pinned_url(url: str, address: str) -> str:
    """Return the same URL pointing at the validated address."""
    parts = urlsplit(url)
    host = f"[{address}]" if ":" in address else address
    netloc = f"{host}:{parts.port}" if parts.port else host
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


def _read_capped(response: httpx.Response, max_bytes: int) -> str:
    """Read at most ``max_bytes`` of the body so a huge document cannot exhaust memory."""
    raw = response.content[:max_bytes]
    charset = response.encoding or "utf-8"
    try:
        return raw.decode(charset, errors="replace")
    except LookupError:
        return raw.decode("utf-8", errors="replace")


def _looks_like_feed(body: str) -> bool:
    """Report whether a body is an RSS, Atom, or RDF feed document."""
    head = body.lstrip()[:2048].lower()
    return any(marker in head for marker in ("<rss", "<feed", "<rdf:rdf", "<channel", "<?xml")) and (
        "<rss" in body[:4096].lower() or "<feed" in body[:4096].lower() or "<rdf" in body[:4096].lower()
    )
