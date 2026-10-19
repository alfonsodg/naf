"""Resolver policy: only globally routable addresses may be contacted."""

import socket

import pytest

from app.core import resolver
from app.core.feed_urls import FeedURLError
from app.core.resolver import resolve_host_addresses, select_public_address


@pytest.mark.parametrize(
    "address",
    ["127.0.0.1", "10.0.0.5", "172.16.0.1", "192.168.1.1", "169.254.169.254", "0.0.0.0", "224.0.0.1", "::1"],  # noqa: S104
)
def test_forbidden_addresses_are_refused(address: str) -> None:
    """A forbidden address is refused and the reason names it."""
    with pytest.raises(FeedURLError) as excinfo:
        select_public_address("host.test", [address])

    assert address in str(excinfo.value)


def test_the_refusal_names_the_kind_of_address() -> None:
    """The report explains which kind of address was found."""
    with pytest.raises(FeedURLError) as excinfo:
        select_public_address("host.test", ["127.0.0.1"])

    assert "loopback" in str(excinfo.value)


def test_a_public_address_is_accepted() -> None:
    """A globally routable address is the one to contact."""
    assert select_public_address("host.test", ["93.184.216.34"]) == "93.184.216.34"


def test_one_forbidden_address_refuses_the_whole_host() -> None:
    """A host with any forbidden address is refused, even with a public one."""
    with pytest.raises(FeedURLError):
        select_public_address("host.test", ["93.184.216.34", "10.0.0.5"])


def test_an_empty_resolution_is_refused() -> None:
    """A host that resolves to nothing cannot be contacted."""
    with pytest.raises(FeedURLError):
        select_public_address("host.test", [])


def test_an_unusable_address_is_refused() -> None:
    """An address that is not an IP is never contacted."""
    with pytest.raises(FeedURLError):
        select_public_address("host.test", ["not-an-address"])


async def test_resolution_collects_every_address(monkeypatch: pytest.MonkeyPatch) -> None:
    """The resolver returns the distinct addresses of the host."""
    monkeypatch.setattr(resolver, "_resolve_addresses", _fixed(["93.184.216.34", "93.184.216.34"]))

    assert await resolve_host_addresses("host.test") == ["93.184.216.34"]


async def test_a_resolution_failure_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    """A name that does not resolve surfaces the resolver failure."""

    async def failing(host: str, port: int) -> list[str]:
        raise socket.gaierror("Name or service not known")

    monkeypatch.setattr(resolver, "_resolve_addresses", failing)

    with pytest.raises(socket.gaierror):
        await resolve_host_addresses("host.test")


def _fixed(addresses: list[str]) -> object:
    """Build a resolver double that always answers the same addresses."""

    async def _resolve_addresses(host: str, port: int) -> list[str]:
        """Return the fixed addresses."""
        return list(addresses)

    return _resolve_addresses
