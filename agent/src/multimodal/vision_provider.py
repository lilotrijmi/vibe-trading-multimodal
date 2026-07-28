"""Vision provider interface and concrete implementations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


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