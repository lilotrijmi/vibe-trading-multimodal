"""Multimodal tools registered to the agent."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from src.multimodal.abuse_detector import AbuseDetector
from src.multimodal.url_reader import URLContentSanitizer, URLFetcher
from src.multimodal.vision_provider import VisionProvider


@dataclass(frozen=True)
class _Tool:
    """Minimal tool descriptor."""

    name: str
    description: str
    invoke: Callable[..., str]


def url_read(
    url: str,
    fetcher: URLFetcher,
    sanitizer: URLContentSanitizer,
    abuse: AbuseDetector | None = None,
) -> str:
    """Fetch and sanitize a URL for trading analysis."""
    if abuse is not None:
        abuse.record(url)
        snap = abuse.snapshot(url)
        if snap.is_burst:
            return "Error: URL fetch rate limit exceeded."
    try:
        result = fetcher.fetch(url)
        sanitized = sanitizer.sanitize(result.text, source_url=result.final_url)
    except Exception:
        return "Error: unable to fetch and sanitize URL content."
    if sanitized.was_truncated:
        return sanitized.text + "\n(Note: content was truncated)"
    return sanitized.text


def describe_image(
    image_bytes: bytes,
    prompt: str,
    vision_provider: VisionProvider,
) -> str:
    """Describe an image using the configured vision provider."""
    try:
        result = vision_provider.analyze(image_bytes, prompt)
    except Exception:
        return "Error: unable to analyze image."
    return result.description


class MultimodalToolRegistry:
    """Registry of multimodal tools for the agent."""

    def __init__(
        self,
        url_fetcher: URLFetcher | None = None,
        content_sanitizer: URLContentSanitizer | None = None,
        vision_provider: VisionProvider | None = None,
        abuse_detector: AbuseDetector | None = None,
    ) -> None:
        self._url_fetcher = url_fetcher
        self._sanitizer = content_sanitizer
        self._vision = vision_provider
        self._abuse = abuse_detector

    def list_tools(self) -> dict[str, _Tool]:
        return {
            "url_read": _Tool(
                name="url_read",
                description="Fetch a URL and return sanitized content for analysis.",
                invoke=self._invoke_url_read,
            ),
            "describe_image": _Tool(
                name="describe_image",
                description="Describe an image using vision model.",
                invoke=self._invoke_describe_image,
            ),
        }

    def _invoke_url_read(self, url: str) -> str:
        if self._url_fetcher is None or self._sanitizer is None:
            return "Error: URL reader is not configured."
        return url_read(
            url,
            fetcher=self._url_fetcher,
            sanitizer=self._sanitizer,
            abuse=self._abuse,
        )

    def _invoke_describe_image(self, image_bytes: bytes, prompt: str) -> str:
        if self._vision is None:
            return "Error: vision provider is not configured."
        return describe_image(
            image_bytes,
            prompt,
            vision_provider=self._vision,
        )
