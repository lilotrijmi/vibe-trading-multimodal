"""Multimodal subsystem initialization.

Bootstraps image pipeline, vision provider, URL reader, and SQLite DB at app
startup. Reads config from env vars; degrades gracefully when optional
dependencies (e.g. ``langchain-anthropic``) are missing.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _build_vision_provider() -> Any:
    """Build vision provider from env vars (multi-provider with fallback).

    Reads:
      - ``VISION_PROVIDER``: openai | anthropic | ollama
      - ``VISION_FALLBACK_PROVIDERS``: comma-separated fallback list
      - ``VISION_MODEL``: model name (default per provider)
      - ``OPENAI_API_KEY`` / ``ANTHROPIC_API_KEY`` / ``OLLAMA_BASE_URL``

    Returns ``NoOpVisionProvider`` if no provider is configured. Wraps multiple
    providers in ``ChainFallbackProvider`` for resilience.
    """
    primary_name = os.environ.get("VISION_PROVIDER", "").lower()
    fallback_names = [
        n.strip().lower()
        for n in os.environ.get("VISION_FALLBACK_PROVIDERS", "").split(",")
        if n.strip()
    ]
    providers: list = []

    def _make(name: str) -> Any:
        if name in ("openai", "gpt-4o", "gpt-4-vision"):
            return _make_openai_provider()
        if name in ("anthropic", "claude"):
            return _make_Anthropic_provider()
        if name == "ollama":
            return _make_ollama_provider()
        return None

    primary = _make(primary_name) if primary_name else None
    if primary is not None:
        providers.append(primary)
    for name in fallback_names:
        p = _make(name)
        if p is not None:
            providers.append(p)

    # Lazy import here to keep the module import cost low.
    from src.multimodal.vision_provider import (
        ChainFallbackProvider,
        NoOpVisionProvider,
    )

    if not providers:
        logger.info("vision provider: NoOp (no VISION_PROVIDER configured)")
        return NoOpVisionProvider()
    if len(providers) == 1:
        return providers[0]
    return ChainFallbackProvider(providers)


def _make_openai_provider() -> Any:
    """OpenAI-compatible vision via ChatOpenAI (also works with proxies)."""
    from langchain_openai import ChatOpenAI

    from src.multimodal.vision_provider import OpenAICompatibleVisionProvider

    return OpenAICompatibleVisionProvider(
        client=ChatOpenAI(
            model=os.environ.get("VISION_MODEL", "gpt-4o"),
            api_key=os.environ.get("OPENAI_API_KEY"),
        ),
        model=os.environ.get("VISION_MODEL", "gpt-4o"),
    )


def _make_Anthropic_provider() -> Any:
    """Anthropic Messages API. Requires optional ``langchain-anthropic``."""
    try:
        from langchain_community.chat_models import ChatAnthropic  # type: ignore
    except ImportError:
        logger.warning(
            "VISION_PROVIDER=anthropic but langchain-community is not installed; "
            "install with: pip install langchain-community"
        )
        return None
    from src.multimodal.vision_provider import GenflowAiVisionProvider

    return GenflowAiVisionProvider(
        client=ChatAnthropic(  # type: ignore[call-arg]
            model=os.environ.get("VISION_MODEL", "GenflowAi-3.5-GenflowAi"),
            anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY"),
        ),
        model=os.environ.get("VISION_MODEL", "GenflowAi-3.5-GenflowAi"),
    )


def _make_ollama_provider() -> Any:
    """Ollama local server. Requires optional ``ollama`` Python client."""
    try:
        import ollama  # type: ignore
    except ImportError:
        logger.warning(
            "VISION_PROVIDER=ollama but ollama package is not installed; "
            "install with: pip install ollama"
        )
        return None
    from src.multimodal.vision_provider import OllamaVisionProvider

    host = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    return OllamaVisionProvider(
        client=ollama.Client(host=host),
        model=os.environ.get("VISION_MODEL", "llama3.2-vision"),
        host=host,
    )


def _build_http_client() -> Any:
    """HTTP client for URL fetches."""
    import httpx

    return httpx.Client(
        timeout=10.0,
        follow_redirects=True,
        headers={"User-Agent": "Vibe-Trading-Multimodal/1.0"},
    )


def init_multimodal_subsystem() -> None:
    """Initialize image pipeline, vision provider, URL reader, and DB.

    Called from ``api_server.py`` startup hook. Safe to call multiple times —
    the most recent configuration wins.
    """
    from src.api.multimodal_routes import configure as configure_routes
    from src.api.multimodal_routes import configure_integration
    from src.db.session import init_db
    from src.multimodal.image_pipeline import ImagePipeline
    from src.multimodal.url_reader import SSRFGuard, URLContentSanitizer, URLFetcher

    storage_dir = _resolve_writable_path(
        "MULTIMODAL_STORAGE_DIR",
        fallback=Path("/app/agent/data/multimodal"),
    )
    db_path_str = os.environ.get("VIBE_TRADING_DB_PATH")
    if db_path_str:
        db_path = _resolve_writable_path_from(
            Path(db_path_str).parent, filename=Path(db_path_str).name
        )
    else:
        db_path = _resolve_writable_path(
            "VIBE_TRADING_DB_PATH",
            fallback=Path("/app/agent/data/vibe_trading.db"),
        )
    init_db(db_path)
    configure_routes(pipeline=ImagePipeline(), storage_dir=storage_dir)

    vision = _build_vision_provider()
    if vision is not None:
        configure_integration(vision_provider=vision)

    fetcher = URLFetcher(
        guard=SSRFGuard(),
        http_client=_build_http_client(),
        max_bytes=50_000_000,
    )
    sanitizer = URLContentSanitizer(max_chars=32_000)
    configure_integration(url_reader=fetcher, content_sanitizer=sanitizer)
    logger.info("multimodal subsystem initialized")


def _is_writable_dir(path: Path) -> bool:
    """Return True if ``path`` exists (or can be created) and is writable."""
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError:
        return False
    test_file = path / ".vibe_trading_writable_test"
    try:
        test_file.touch()
        test_file.unlink()
    except OSError:
        return False
    return True


def _resolve_writable_path_from(parent: Path, filename: str) -> Path:
    """Return a writable path under ``parent/filename``; fall back to /tmp."""
    parent = Path(parent)
    if _is_writable_dir(parent):
        return parent / filename
    fallback = Path("/tmp/vibe_trading")
    logger.warning(
        "db/storage dir %s is not writable; falling back to %s",
        parent,
        fallback,
    )
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback / filename


def _resolve_writable_path(env_var: str, fallback: Path) -> Path:
    """Resolve a path from env, falling back to /tmp if not writable."""
    raw = os.environ.get(env_var)
    candidate = Path(raw) if raw else fallback
    if _is_writable_dir(candidate.parent):
        return candidate
    fb = Path("/tmp/vibe_trading") / candidate.name
    logger.warning(
        "%s=%s not writable; falling back to %s",
        env_var,
        candidate,
        fb,
    )
    fb.parent.mkdir(parents=True, exist_ok=True)
    return fb
