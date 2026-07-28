"""Safe URL reader with SSRF protection."""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from src.multimodal.exceptions import URLFetchError, URLSecurityError


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


@dataclass(frozen=True)
class FetchResult:
    """Result of URL fetch."""

    url: str
    final_url: str
    text: str
    title: str
    status: int


class URLFetcher:
    """Fetches URL content with safety limits."""

    def __init__(
        self,
        guard: SSRFGuard,
        http_client: Any,
        max_bytes: int = 50_000_000,
        timeout: float = 10.0,
    ) -> None:
        self._guard = guard
        self._client = http_client
        self._max_bytes = max_bytes
        self._timeout = timeout

    def fetch(self, url: str) -> FetchResult:
        self._guard.validate(url)
        try:
            response = self._client.get(
                url,
                timeout=self._timeout,
                follow_redirects=True,
            )
        except Exception as exc:
            raise URLFetchError(f"fetch failed: {exc}") from exc

        if response.status_code >= 400:
            raise URLFetchError(
                f"HTTP {response.status_code} for {url}"
            )

        ctype = response.headers.get("content-type", "").lower()
        if "text/html" not in ctype and "text/plain" not in ctype and "application/xhtml" not in ctype:
            raise URLFetchError(
                f"unsupported content-type: {ctype!r}"
            )

        if len(response.content) > self._max_bytes:
            raise URLFetchError(
                f"content too large: {len(response.content)} bytes"
            )

        try:
            import trafilatura

            extracted = trafilatura.extract(
                response.text,
                include_comments=False,
                include_tables=True,
                favor_recall=True,
            )
            text = extracted or response.text
            title = ""
            metadata = trafilatura.extract_metadata(response.text)
            if metadata and metadata.title:
                title = metadata.title
        except ImportError:
            text = response.text
            title = ""

        return FetchResult(
            url=url,
            final_url=response.url,
            text=text,
            title=title,
            status=response.status_code,
        )


@dataclass(frozen=True)
class SanitizedContent:
    """Sanitized URL content ready for LLM."""

    text: str
    source_url: str
    was_truncated: bool


class URLContentSanitizer:
    """Sanitizes URL content before injecting into agent context."""

    DELIMITER = "<<UNTRUSTED_URL_CONTENT>>"

    def __init__(self, max_chars: int = 32_000) -> None:
        self._max_chars = max_chars

    def sanitize(self, text: str, source_url: str) -> SanitizedContent:
        cleaned = text.replace(self.DELIMITER, "").replace("</UNTRUSTED_URL_CONTENT>", "")

        try:
            import bleach

            cleaned = bleach.clean(
                cleaned,
                tags=[],
                attributes={},
                strip=True,
                strip_comments=True,
            )
        except ImportError:
            import re

            cleaned = re.sub(r"<[^>]+>", "", cleaned)

        was_truncated = False
        if len(cleaned) > self._max_chars:
            cleaned = cleaned[: self._max_chars]
            was_truncated = True
            cleaned += "\n\n[... (truncated) ...]"

        wrapped = (
            f"Source: {source_url}\n"
            f"{'-' * 40}\n"
            f"{cleaned}"
        )

        return SanitizedContent(
            text=wrapped,
            source_url=source_url,
            was_truncated=was_truncated,
        )
