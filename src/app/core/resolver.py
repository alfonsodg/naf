"""Resolve candidate hosts and refuse addresses that are not globally routable.

A hostname is not a target, it is a promise about one. The shape checks in
:mod:`app.core.feed_urls` only read the name, so a public name that points at
a private address passes every rule. Resolving the name before the connection
closes that gap, and pinning the resolved address closes the gap between the
check and the socket.
"""

import asyncio
import ipaddress
import socket

from app.core.feed_urls import FeedURLError


async def resolve_host_addresses(host: str, port: int = 443) -> list[str]:
    """Return every address the host resolves to.

    Raises :class:`socket.gaierror` when the name cannot be resolved, so the
    caller can report an unreachable host instead of a blocked one.
    """
    return sorted(set(await _resolve_addresses(host, port)))


async def _resolve_addresses(host: str, port: int) -> list[str]:
    """Ask the resolver for the addresses of a host."""
    loop = asyncio.get_running_loop()
    infos = await loop.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    return [str(info[4][0]) for info in infos]


def select_public_address(host: str, addresses: list[str]) -> str:
    """Return the address to contact, refusing any forbidden result.

    A host that resolves to a private, loopback, link-local, reserved, or
    metadata address is refused even when the name itself looks harmless.
    """
    if not addresses:
        raise FeedURLError(f"host {host} did not resolve to any address")

    for candidate in addresses:
        try:
            address = ipaddress.ip_address(candidate)
        except ValueError as exc:
            raise FeedURLError(f"host {host} resolved to an unusable address {candidate}") from exc
        if _is_forbidden(address):
            raise FeedURLError(f"host {host} resolves to {candidate}, which is a {_forbidden_reason(address)} address")

    return addresses[0]


def _is_forbidden(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Report whether an address must never be contacted."""
    return (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_reserved
        or address.is_multicast
        or address.is_unspecified
        or not address.is_global
    )


def _forbidden_reason(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> str:
    """Name the reason an address is refused, so the report is diagnosable."""
    if address.is_loopback:
        return "loopback"
    if address.is_link_local:
        return "link-local"
    if address.is_private:
        return "private"
    if address.is_multicast:
        return "multicast"
    if address.is_reserved:
        return "reserved"
    if address.is_unspecified:
        return "unspecified"
    return "non-public"
