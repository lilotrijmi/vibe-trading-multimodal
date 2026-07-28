"""Vision provider interface and concrete implementations."""

from __future__ import annotations

import base64
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Protocol

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


class _ChatClient(Protocol):
    def chat(self, **kwargs: Any) -> dict[str, Any]: ...


class OpenAICompatibleVisionProvider(VisionProvider):
    """Vision provider for OpenAI-compatible chat APIs."""

    def __init__(self, client: _ChatClient, model: str) -> None:
        self._client = client
        self._model = model

    def analyze(self, image: bytes, prompt: str) -> VisionResult:
        b64 = base64.b64encode(image).decode("ascii")
        try:
            response = self._client.chat(
                model=self._model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/png;base64,{b64}"},
                            },
                        ],
                    }
                ],
            )
        except Exception as exc:
            raise VisionProviderError(
                f"OpenAI-compatible vision call failed: {exc}"
            ) from exc

        try:
            content = response["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise VisionProviderError(
                f"unexpected response shape: {response!r}"
            ) from exc

        if not isinstance(content, str) or not content.strip():
            raise VisionProviderError("provider returned empty content")

        return VisionResult(description=content.strip(), provider=self._model)


class _GenflowAiClient(Protocol):
    def create(self, **kwargs: Any) -> Any: ...


class GenflowAiVisionProvider(VisionProvider):
    """Vision provider for Anthropic Messages API."""

    def __init__(self, client: _GenflowAiClient, model: str) -> None:
        self._client = client
        self._model = model

    def analyze(self, image: bytes, prompt: str) -> VisionResult:
        b64 = base64.b64encode(image).decode("ascii")
        try:
            response = self._client.create(
                model=self._model,
                max_tokens=1024,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/png",
                                    "data": b64,
                                },
                            },
                            {"type": "text", "text": prompt},
                        ],
                    }
                ],
            )
        except Exception as exc:
            raise VisionProviderError(
                f"GenflowAi vision call failed: {exc}"
            ) from exc

        try:
            blocks = response.content
            text = "".join(getattr(b, "text", "") for b in blocks).strip()
        except (AttributeError, TypeError) as exc:
            raise VisionProviderError(
                f"unexpected response shape: {response!r}"
            ) from exc

        if not text:
            raise VisionProviderError("provider returned empty content")

        return VisionResult(description=text, provider=self._model)


class OllamaVisionProvider(VisionProvider):
    """Vision provider for local Ollama API."""

    def __init__(self, client: _ChatClient, model: str, host: str) -> None:
        self._client = client
        self._model = model
        self._host = host

    def analyze(self, image: bytes, prompt: str) -> VisionResult:
        b64 = base64.b64encode(image).decode("ascii")
        try:
            response = self._client.chat(
                model=f"{self._model}:latest",
                messages=[{"role": "user", "content": prompt}],
                images=[f"data:image/png;base64,{b64}"],
            )
        except Exception as exc:
            raise VisionProviderError(
                f"Ollama vision call failed: {exc}"
            ) from exc

        try:
            content = response["message"]["content"]
        except (KeyError, TypeError) as exc:
            raise VisionProviderError(
                f"unexpected response shape: {response!r}"
            ) from exc

        if not isinstance(content, str) or not content.strip():
            raise VisionProviderError("provider returned empty content")

        return VisionResult(description=content.strip(), provider=self._model)