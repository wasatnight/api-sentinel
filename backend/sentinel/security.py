"""HTTPX transport whose TCP sockets only use pre-validated public numeric addresses."""

import asyncio
import ipaddress
import socket
import ssl

import certifi
import httpcore
import httpx
from httpcore._backends.auto import AutoBackend

from .schemas import ServiceInput


class DestinationBlocked(Exception):
    pass


class DNSFailure(Exception):
    pass


def public_ip(value: str) -> bool:
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return False
    if not address.is_global or address.is_multicast or address.is_reserved:
        return False
    if isinstance(address, ipaddress.IPv6Address):
        if address.ipv4_mapped:
            return public_ip(str(address.ipv4_mapped))
        # Do not route through transition/tunneling prefixes that can encode internal IPv4.
        if address.sixtofour or address.teredo:
            return False
        if address in ipaddress.ip_network("64:ff9b::/96") or address in ipaddress.ip_network(
            "64:ff9b:1::/48"
        ):
            return False
    return True


def validate_destination(url: str):
    try:
        ServiceInput.validate_url(url)
    except ValueError:
        raise DestinationBlocked("Destination blocked by the network policy.") from None


async def resolve_public(host: str, port: int) -> list[str]:
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        try:
            rows = await asyncio.wait_for(
                asyncio.get_running_loop().getaddrinfo(
                    host, port, type=socket.SOCK_STREAM, proto=socket.IPPROTO_TCP
                ),
                timeout=4,
            )
        except TimeoutError:
            raise DNSFailure("DNS resolution timed out.") from None
        except socket.gaierror:
            raise DNSFailure("DNS resolution failed.") from None
        addresses = list(dict.fromkeys(row[4][0] for row in rows))
    else:
        addresses = [str(literal)]
    if not addresses:
        raise DNSFailure("DNS did not return any addresses.")
    # Reject mixed public/private answers rather than choosing a public address from them.
    if not all(public_ip(ip) for ip in addresses):
        raise DestinationBlocked("DNS returned a non-public destination.")
    return addresses


class PublicNetworkBackend(AutoBackend):
    async def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
        addresses = await resolve_public(host, port)
        # The OS receives only this validated IP, never the hostname for a second DNS lookup.
        # HTTPCore still uses its original origin hostname for SNI and certificate verification.
        last_error = None
        for ip in addresses:
            try:
                return await super().connect_tcp(ip, port, timeout, local_address, socket_options)
            except (httpcore.ConnectError, httpcore.ConnectTimeout) as error:
                last_error = error
        raise last_error or DNSFailure("No usable addresses.")


class PublicTransport(httpx.AsyncHTTPTransport):
    def __init__(self):
        # Small, version-pinned HTTPX/HTTPCore adapter. Inherited request mapping preserves
        # original Host/SNI and translates core exceptions. No proxies, UDS or socket reuse.
        self._pool = httpcore.AsyncConnectionPool(
            ssl_context=ssl.create_default_context(cafile=certifi.where()),
            network_backend=PublicNetworkBackend(),
            max_connections=1,
            max_keepalive_connections=0,
            retries=0,
        )
