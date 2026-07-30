"""Tests for the multimodal vision provider's provider name resolution.

Verifies that aliases like ``genflow`` (lowercase) and ``minimax`` resolve to
the OpenAI-compatible provider so that users can pick a custom OpenAI-style
gateway in Settings without writing code.
"""

from __future__ import annotations

import os
import sys

import pytest


def _purge_env() -> None:
    """Remove all VISION_* / OPENAI_* / ANTHROPIC_* env vars before each test."""
    keys = [
        "VISION_ENABLED",
        "VISION_PROVIDER",
        "VISION_MODEL",
        "OPENAI_API_KEY",
        "OPENAI_BASE_URL",
        "ANTHROPIC_API_KEY",
    ]
    for k in keys:
        os.environ.pop(k, None)


def _import_module():
    """Return the multimodal_routes module (loaded once per test)."""
    if "src.api.multimodal_routes" in sys.modules:
        return sys.modules["src.api.multimodal_routes"]
    return __import__("src.api.multimodal_routes", fromlist=["_get_active_vision_provider"])


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Reset VISION_* env before each test."""
    _purge_env()
    yield


def test_genflow_alias_resolves_to_openai_compatible() -> None:
    os.environ["OPENAI_API_KEY"] = "gf-test-key"
    os.environ["VISION_PROVIDER"] = "genflow"
    os.environ["VISION_MODEL"] = "minimax-m3"
    os.environ["VISION_ENABLED"] = "true"
    mod = _import_module()
    provider = mod._get_active_vision_provider()
    assert provider is not None
    assert type(provider).__name__ == "OpenAICompatibleVisionProvider"
    assert provider._model == "minimax-m3"


def test_minimax_alias_resolves_to_openai_compatible() -> None:
    os.environ["OPENAI_API_KEY"] = "gf-test-key"
    os.environ["VISION_PROVIDER"] = "minimax"
    os.environ["VISION_MODEL"] = "minimax-vision"
    os.environ["VISION_ENABLED"] = "true"
    mod = _import_module()
    provider = mod._get_active_vision_provider()
    assert provider is not None
    assert type(provider).__name__ == "OpenAICompatibleVisionProvider"


def test_explicit_openai_still_works() -> None:
    os.environ["OPENAI_API_KEY"] = "sk-test"
    os.environ["VISION_PROVIDER"] = "openai"
    os.environ["VISION_MODEL"] = "gpt-4o"
    os.environ["VISION_ENABLED"] = "true"
    mod = _import_module()
    provider = mod._get_active_vision_provider()
    assert provider is not None
    assert type(provider).__name__ == "OpenAICompatibleVisionProvider"


def test_disabled_returns_none() -> None:
    os.environ["OPENAI_API_KEY"] = "sk-test"
    os.environ["VISION_PROVIDER"] = "openai"
    os.environ["VISION_MODEL"] = "gpt-4o"
    os.environ["VISION_ENABLED"] = "false"
    mod = _import_module()
    provider = mod._get_active_vision_provider()
    assert provider is None


def test_no_api_key_returns_none() -> None:
    os.environ["VISION_PROVIDER"] = "openai"
    os.environ["VISION_MODEL"] = "gpt-4o"
    os.environ["VISION_ENABLED"] = "true"
    mod = _import_module()
    provider = mod._get_active_vision_provider()
    assert provider is None


def test_unknown_provider_returns_noop() -> None:
    os.environ["OPENAI_API_KEY"] = "sk-test"
    os.environ["VISION_PROVIDER"] = "some-future-provider"
    os.environ["VISION_MODEL"] = "model"
    os.environ["VISION_ENABLED"] = "true"
    mod = _import_module()
    provider = mod._get_active_vision_provider()
    # Unknown providers should return NoOp (graceful fallback) rather than None,
    # so the chat endpoint can still attach a "(no description)" context.
    assert provider is not None
    assert type(provider).__name__ == "NoOpVisionProvider"
