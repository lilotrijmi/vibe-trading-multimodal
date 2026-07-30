"""Vision provider interface and concrete implementations."""

from __future__ import annotations

import base64
import os
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
    """Vision provider for OpenAI-compatible chat APIs.

    Accepts either a raw client with a ``chat()`` method (returns a dict) or a
    LangChain ``ChatOpenAI`` (responds to ``invoke()`` with an ``AIMessage``).
    The provider auto-detects which interface is in use.
    """

    def __init__(self, client: Any, model: str) -> None:
        self._client = client
        self._model = model

    def analyze(self, image: bytes, prompt: str) -> VisionResult:
        b64 = base64.b64encode(image).decode("ascii")
        messages = [
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
        ]

        response_repr = "<unavailable>"
        content: Any = None
        try:
            if hasattr(self._client, "chat") and callable(getattr(self._client, "chat", None)):
                # Raw httpx-like client: returns a dict with "choices".
                response = self._client.chat(model=self._model, messages=messages)
                response_repr = repr(response)[:500]
                content = response["choices"][0]["message"]["content"]
            else:
                # LangChain chat model: invoke() returns an AIMessage.
                # Some OpenAI-compatible gateways (e.g. Genflow) ignore the
                # ``stream=False`` flag and return an SSE-formatted body
                # (``data: {...}``) instead of a JSON object. LangChain's
                # parser crashes on that ("'str' object has no attribute
                # 'model_dump'"). When that happens, fall back to a direct
                # httpx request with manual SSE parsing.
                try:
                    lc_messages = self._lc_messages(prompt, b64)
                    response = self._client.invoke(lc_messages)
                    response_repr = repr(response)[:500]
                    content = (
                        response.content if hasattr(response, "content") else str(response)
                    )
                except Exception as inner_exc:
                    err_str = str(inner_exc)
                    if "'str' object has no attribute 'model_dump'" in err_str or "model_dump" in err_str:
                        content = self._invoke_via_raw_http(prompt, b64, messages)
                    else:
                        raise
        except VisionProviderError:
            raise
        except Exception as exc:
            raise VisionProviderError(
                f"OpenAI-compatible vision call failed: {exc}"
            ) from exc

        if not isinstance(content, str) or not content.strip():
            raise VisionProviderError(
                f"provider returned empty content for model={self._model!r}. "
                f"This often means the model is not actually vision-capable on the "
                f"configured endpoint (e.g. an OpenAI-compatible gateway may not "
                f"route a text model to a vision backend). Try a known vision "
                f"model (gpt-4o, glm-4v, claude-3.5-sonnet) or a different "
                f"provider. Response: {response_repr}"
            )

        return VisionResult(description=content.strip(), provider=self._model)

    def _invoke_via_raw_http(
        self, prompt: str, b64: str, messages: list[dict[str, Any]]
    ) -> str:
        """Fallback when LangChain can't parse the provider's response.

        Bypasses LangChain entirely: builds a raw httpx POST to the chat
        completions endpoint and manually parses a Server-Sent Events
        (SSE) stream if ``stream=False`` is ignored by the gateway.
        Returns the concatenated assistant content.
        """
        import json
        import httpx  # local import — provider may run without it otherwise

        base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            raise VisionProviderError("OPENAI_API_KEY not set")

        # Try with stream=False first; if the gateway ignores it, fall back to
        # parsing SSE.
        payload = {
            "model": self._model,
            "stream": False,
            "messages": messages,
            "max_tokens": 1024,
        }
        try:
            response = httpx.post(
                f"{base_url.rstrip('/')}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=60.0,
            )
        except Exception as exc:
            raise VisionProviderError(f"raw HTTP call failed: {exc}") from exc

        text = response.text
        # Plain JSON response
        if response.headers.get("content-type", "").startswith("application/json"):
            try:
                data = response.json()
                return data["choices"][0]["message"]["content"] or ""
            except Exception as exc:
                raise VisionProviderError(
                    f"unexpected JSON response: {text[:300]}"
                ) from exc

        # SSE response: collect content from each "data: {...}" chunk.
        if text.lstrip().startswith("data:"):
            chunks: list[str] = []
            for line in text.splitlines():
                line = line.strip()
                if not line.startswith("data:"):
                    continue
                payload_str = line[len("data:"):].strip()
                if not payload_str or payload_str == "[DONE]":
                    continue
                try:
                    data = json.loads(payload_str)
                    delta = data["choices"][0].get("delta") or {}
                    chunk = delta.get("content")
                    if chunk:
                        chunks.append(chunk)
                except Exception:
                    continue
            return "".join(chunks)

        raise VisionProviderError(
            f"unexpected response content-type and body: {response.headers.get('content-type')} | {text[:300]}"
        )

    def _lc_messages(self, prompt: str, b64: str) -> list:
        """Build a LangChain HumanMessage list with image+text content."""
        try:
            from langchain_core.messages import HumanMessage
        except ImportError as exc:
            raise VisionProviderError(
                "LangChain messages not available; cannot use ChatOpenAI client"
            ) from exc

        return [
            HumanMessage(
                content=[
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{b64}"},
                    },
                ]
            )
        ]


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
                images=[b64],
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