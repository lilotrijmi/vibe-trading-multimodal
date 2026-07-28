from __future__ import annotations

import pytest

from src.multimodal.vision_provider import (
    VisionProvider,
    VisionResult,
    NoOpVisionProvider,
)


class FakeVisionProvider(VisionProvider):
    def __init__(self, response: str) -> None:
        self._response = response
        self.calls: list[tuple[bytes, str]] = []

    def analyze(self, image: bytes, prompt: str) -> VisionResult:
        self.calls.append((image, prompt))
        return VisionResult(description=self._response, provider="fake")


def test_noop_provider_returns_empty_description() -> None:
    provider = NoOpVisionProvider()
    result = provider.analyze(b"image-bytes", "describe this chart")
    assert result.description == ""
    assert result.provider == "noop"


def test_fake_provider_returns_configured_response() -> None:
    provider = FakeVisionProvider("uptrend with resistance at 100")
    result = provider.analyze(b"image-bytes", "describe")
    assert result.description == "uptrend with resistance at 100"
    assert result.provider == "fake"
    assert len(provider.calls) == 1


def test_vision_result_is_immutable() -> None:
    from dataclasses import FrozenInstanceError

    result = VisionResult(description="x", provider="fake")
    with pytest.raises(FrozenInstanceError):
        result.description = "y"  # type: ignore[misc]