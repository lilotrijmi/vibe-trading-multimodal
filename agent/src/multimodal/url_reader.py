"""Safe URL reader with SSRF protection."""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urlparse

from src.multimodal.exceptions import URLSecurityError


_ALLOWED_SCHEMES = frozenset({"http", "https"})


@dataclass(frozen=True)
class URLInfo:
    """Validated URL information."""

    url: str
    scheme: str
    hostname: str
    port: int | None


class SSRFGuard:
    """Validates URL scheme and resolves IP to detect SSRF."""

    def __init__(self, allow_private: bool = False) -> None:
        self._allow_private = allow_private

    def check_scheme(self, url: str) -> None:
        parsed = urlparse(url)
        if parsed.scheme.lower() not in _ALLOWED_SCHEMES:
            raise URLSecurityError(
                f"scheme not allowed: {parsed.scheme!r}"
            )

    def check_ip(self, ip: str) -> None:
        if self._allow_private:
            return
        try:
            addr = ipaddress.ip_address(ip)
        except ValueError as exc:
            raise URLSecurityError(f"invalid IP: {ip!r}") from exc
        if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved:
            raise URLSecurityError(f"blocked IP: {ip}")

    def resolve(self, hostname: str) -> str:
        try:
            infos = socket.getaddrinfo(hostname, None)
        except socket.gaierror as exc:
            raise URLSecurityError(f"DNS resolution failed: {hostname}") from exc
        if not infos:
            raise URLSecurityError(f"DNS resolution returned no results: {hostname}")
        resolved = infos[0][4][0]
        self.check_ip(resolved)
        return resolved

    def validate(self, url: str) -> URLInfo:
        self.check_scheme(url)
        parsed = urlparse(url)
        if not parsed.hostname:
            raise URLSecurityError(f"URL missing hostname: {url!r}")
        self.resolve(parsed.hostname)
        return URLInfo(
            url=url,
            scheme=parsed.scheme.lower(),
            hostname=parsed.hostname,
            port=parsed.port,
        )
