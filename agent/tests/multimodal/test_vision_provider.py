from __future__ import annotations

import base64

import pytest

from src.multimodal.vision_provider import (
    ChainFallbackProvider,
    GenflowAiVisionProvider,
    NoOpVisionProvider,
    OpenAICompatibleVisionProvider,
    OllamaVisionProvider,
    VisionProvider,
    VisionResult,
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


def test_openai_compatible_provider_sends_image_to_api() -> None:
    captured: dict = {}

    class FakeClient:
        def chat(self, **kwargs):
            captured["kwargs"] = kwargs
            return {
                "choices": [
                    {"message": {"content": "uptrend, support at 90"}}
                ]
            }

    client = FakeClient()
    provider = OpenAICompatibleVisionProvider(
        client=client,  # type: ignore[arg-type]
        model="gpt-4o",
    )
    result = provider.analyze(b"fake-image-bytes", "describe this chart")
    assert result.description == "uptrend, support at 90"
    assert "gpt-4o" in captured["kwargs"]["model"]
    user_msg = captured["kwargs"]["messages"][0]
    assert user_msg["role"] == "user"
    content = user_msg["content"]
    assert isinstance(content, list)
    image_block = next(b for b in content if b["type"] == "image_url")
    assert image_block["image_url"]["url"].startswith("data:image/png;base64,")


def test_openai_compatible_provider_raises_on_empty_response() -> None:
    class FakeClient:
        def chat(self, **kwargs):
            return {"choices": [{"message": {"content": ""}}]}

    provider = OpenAICompatibleVisionProvider(
        client=FakeClient(),  # type: ignore[arg-type]
        model="gpt-4o",
    )
    with pytest.raises(VisionProviderError):
        provider.analyze(b"bytes", "prompt")


def test_openai_compatible_provider_raises_on_error() -> None:
    class FakeClient:
        def chat(self, **kwargs):
            raise RuntimeError("network failure")

    provider = OpenAICompatibleVisionProvider(
        client=FakeClient(),  # type: ignore[arg-type]
        model="gpt-4o",
    )
    with pytest.raises(VisionProviderError):
        provider.analyze(b"bytes", "prompt")


def test_GenflowAi_provider_uses_messages_api() -> None:
    captured: dict = {}

    class FakeClient:
        def create(self, **kwargs):
            captured["kwargs"] = kwargs
            return type(
                "Resp",
                (),
                {"content": [type("Block", (), {"text": "support at 90, resistance at 110"})()]},
            )()

    provider = GenflowAiVisionProvider(
        client=FakeClient(),  # type: ignore[arg-type]
        model="GenflowAi-3.5-GenflowAi",
    )
    result = provider.analyze(b"fake-image", "describe")
    assert "support at 90" in result.description
    assert captured["kwargs"]["model"] == "GenflowAi-3.5-GenflowAi"
    messages = captured["kwargs"]["messages"]
    assert messages[0]["role"] == "user"
    content = messages[0]["content"]
    assert isinstance(content, list)
    image_block = next(b for b in content if b["type"] == "image")
    assert image_block["source"]["type"] == "base64"
    assert image_block["source"]["media_type"] == "image/png"


def test_GenflowAi_provider_raises_on_empty_text() -> None:
    class FakeClient:
        def create(self, **kwargs):
            return type("Resp", (), {"content": []})()

    provider = GenflowAiVisionProvider(
        client=FakeClient(),  # type: ignore[arg-type]
        model="GenflowAi-3.5-GenflowAi",
    )
    with pytest.raises(VisionProviderError):
        provider.analyze(b"bytes", "prompt")


def test_ollama_provider_uses_ollama_api() -> None:
    captured: dict = {}

    class FakeClient:
        def chat(self, **kwargs):
            captured["kwargs"] = kwargs
            return {"message": {"content": "local chart description"}}

    provider = OllamaVisionProvider(
        client=FakeClient(),  # type: ignore[arg-type]
        model="llama3.2-vision",
        host="http://localhost:11434",
    )
    result = provider.analyze(b"image-bytes", "describe")
    assert result.description == "local chart description"
    assert "llama3.2-vision" in captured["kwargs"]["model"]
    messages = captured["kwargs"]["messages"]
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "describe"
    images = captured["kwargs"]["images"]
    assert len(images) == 1
    # Ollama expects raw base64, no data URL prefix
    assert images[0] == base64.b64encode(b"image-bytes").decode("ascii")