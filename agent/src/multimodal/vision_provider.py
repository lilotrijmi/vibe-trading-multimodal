"""Vision provider interface and concrete implementations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from src.multimodal.exceptions import VisionProviderError


@dataclass(frozen=True)
class VisionResult:
    """Result from a vision provider analysis."""

    description: str
    provider: str


class VisionProvider(ABC):
    """Abstract base class for vision providers."""

    @abstractmethod
    def analyze(self, image: bytes, prompt: str) -> VisionResult:
        """Analyze an image and return structured description."""


class NoOpVisionProvider(VisionProvider):
    """Fallback provider that returns empty description."""

    def analyze(self, image: bytes, prompt: str) -> VisionResult:
        return VisionResult(description="", provider="noop")


class ChainFallbackProvider(VisionProvider):
    """Try providers in order; return the first successful result.

    Iterates through the configured chain and returns the result from the
    first provider whose ``analyze`` call succeeds. If a provider raises
    :class:`VisionProviderError` it is treated as a fallback and the next
    provider is tried. Any other exception propagates immediately.

    The provider name returned in :class:`VisionResult` is the name of the
    provider that actually served the response, not ``"chain"``.
    """

    def __init__(self, providers: list[VisionProvider]) -> None:
        self._providers = list(providers)

    @property
    def providers(self) -> list[VisionProvider]:
        """Return the configured provider chain (copy)."""
        return list(self._providers)

    def analyze(self, image: bytes, prompt: str) -> VisionResult:
        if not self._providers:
            raise VisionProviderError("vision provider chain is empty")
        last_error: VisionProviderError | None = None
        for provider in self._providers:
            try:
                return provider.analyze(image, prompt)
            except VisionProviderError as exc:
                last_error = exc
                continue
        assert last_error is not None  # loop ran at least once
        raise last_error