"""Public HTTPS allowlist and DNS pinning for the isolated media worker."""

from __future__ import annotations

import ipaddress
import socket
from typing import Any
from urllib.parse import urlsplit

from changgeun.domain.models import DomainError

DOMAINS = ("youtube.com", "googlevideo.com", "ytimg.com", "youtubei.googleapis.com")


def allowed_host(host: str) -> bool:
    return any(host == domain or host.endswith("." + domain) for domain in DOMAINS)


def check_url(url: str, *, media: bool = False) -> str:
    try:
        parts = urlsplit(url)
        host = parts.hostname or ""
        port = parts.port
    except ValueError:
        raise DomainError("media_network_denied") from None
    if (
        parts.scheme != "https"
        or parts.username
        or parts.password
        or port not in {None, 443}
        or not allowed_host(host)
        or len(url) > 16384
        or (media and not host.endswith(".googlevideo.com"))
    ):
        raise DomainError("media_network_denied")
    return host


def public_address(value: str) -> bool:
    try:
        address = ipaddress.ip_address(value)
        return address.is_global and not (
            isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None
        )
    except ValueError:
        return False


class PinnedDNS:
    def __init__(self) -> None:
        self.original = socket.getaddrinfo
        self.cache: dict[tuple[str, int], list[Any]] = {}

    def resolve(
        self,
        host: str,
        port: int,
        family: int = 0,
        type: int = 0,
        proto: int = 0,
        flags: int = 0,
    ) -> list[Any]:
        if not isinstance(host, str) or not allowed_host(host) or int(port) != 443:
            raise DomainError("media_network_denied")
        key = (host, int(port))
        if key not in self.cache:
            rows = self.original(host, port, socket.AF_UNSPEC, socket.SOCK_STREAM)
            if not rows or not all(public_address(str(row[4][0])) for row in rows):
                raise DomainError("media_network_denied")
            self.cache[key] = rows
        return [row for row in self.cache[key] if family in {0, row[0]}]
