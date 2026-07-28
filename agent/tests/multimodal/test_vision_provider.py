from __future__ import annotations

import pytest

from src.multimodal.vision_provider import (
    VisionProvider,
    VisionResult,
    NoOpVisionProvider,
    ChainFallbackProvider,
)
from src.multimodal.exceptions import VisionProviderError


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


class FlakyVisionProvider(VisionProvider):
    def __init__(self, response: str | None, failures: int = 1) -> None:
        self._response = response
        self._remaining_failures = failures
        self.calls = 0

    def analyze(self, image: bytes, prompt: str) -> VisionResult:
        self.calls += 1
        if self._remaining_failures > 0:
            self._remaining_failures -= 1
            raise VisionProviderError("simulated provider failure")
        assert self._response is not None
        return VisionResult(description=self._response, provider="flaky")


def test_chain_fallback_uses_first_provider() -> None:
    primary = FakeVisionProvider("primary-response")
    secondary = FakeVisionProvider("secondary-response")
    chain = ChainFallbackProvider([primary, secondary])

    result = chain.analyze(b"img", "describe")

    assert result.description == "primary-response"
    assert result.provider == "fake"
    assert len(primary.calls) == 1
    assert len(secondary.calls) == 0


def test_chain_fallback_falls_back_on_error() -> None:
    primary = FlakyVisionProvider("primary-response", failures=1)
    secondary = FakeVisionProvider("secondary-response")
    chain = ChainFallbackProvider([primary, secondary])

    result = chain.analyze(b"img", "describe")

    assert result.description == "secondary-response"
    assert primary.calls == 1
    assert len(secondary.calls) == 1


def test_chain_raises_when_all_providers_fail() -> None:
    first = FlakyVisionProvider(None, failures=1)
    second = FlakyVisionProvider(None, failures=1)
    chain = ChainFallbackProvider([first, second])

    with pytest.raises(VisionProviderError):
        chain.analyze(b"img", "describe")
    assert first.calls == 1
    assert second.calls == 1


def test_chain_fallback_raises_when_empty() -> None:
    chain = ChainFallbackProvider([])

    with pytest.raises(VisionProviderError):
        chain.analyze(b"img", "describe")