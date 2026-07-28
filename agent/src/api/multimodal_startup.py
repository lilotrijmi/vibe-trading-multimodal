"""Multimodal subsystem initialization."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _build_vision_provider() -> Any:
    """Build vision provider from env vars (multi-provider with fallback)."""
    primary_name = os.environ.get("VISION_PROVIDER", "").lower()
    fallback_names = [
        n.strip().lower()
        for n in os.environ.get("VISION_FALLBACK_PROVIDERS", "").split(",")
        if n.strip()
    ]
    providers = []

    def _make(name: str) -> Any:
        if name in ("openai", "gpt-4o", "gpt-4-vision"):
            try:
                from langchain_openai import ChatOpenAI
            except ImportError:
                return None
            return OpenAICompatibleVisionProvider(  # type: ignore[name-defined]
                client=ChatOpenAI(
                    model=os.environ.get("VISION_MODEL", "gpt-4o"),
                    api_key=os.environ.get("OPENAI_API_KEY"),
                ),
                model=os.environ.get("VISION_MODEL", "gpt-4o"),
            )
        if name in ("anthropic", "claude"):
            try:
                from langchain_community.chat_models import ChatAnthropic  # type: ignore
            except ImportError:
                return None
            return GenflowAiVisionProvider(  # type: ignore[name-defined]
                client=ChatAnthropic(  # type: ignore[call-arg]
                    model=os.environ.get("VISION_MODEL", "GenflowAi-3.5-GenflowAi"),
                    anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY"),
                ),
                model=os.environ.get("VISION_MODEL", "GenflowAi-3.5-GenflowAi"),
            )
        if name == "ollama":
            try:
                import ollama  # type: ignore
            except ImportError:
                return None
            return OllamaVisionProvider(  # type: ignore[name-defined]
                client=ollama.Client(
                    host=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434"),
                ),
                model=os.environ.get("VISION_MODEL", "llama3.2-vision"),
                host=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434"),
            )
        return None

    primary = _make(primary_name) if primary_name else None
    if primary is not None:
        providers.append(primary)
    for name in fallback_names:
        p = _make(name)
        if p is not None:
            providers.append(p)

    if not providers:
        return NoOpVisionProvider()  # type: ignore[name-defined]
    if len(providers) == 1:
        return providers[0]
    return ChainFallbackProvider(providers)  # type: ignore[name-defined]


def _build_http_client() -> Any:
    import httpx

    return httpx.Client(
        timeout=10.0,
        follow_redirects=True,
        headers={"User-Agent": "Vibe-Trading-Multimodal/1.0"},
    )


def init_multimodal_subsystem() -> None:
    """Initialize image pipeline, vision provider, URL reader, and DB."""
    from src.api.multimodal_routes import configure as configure_routes
    from src.api.multimodal_routes import configure_integration
    from src.db.session import init_db
    from src.multimodal.abuse_detector import AbuseDetector
    from src.multimodal.image_pipeline import ImagePipeline
    from src.multimodal.url_reader import SSRFGuard, URLContentSanitizer, URLFetcher
    from src.multimodal.vision_provider import (
        ChainFallbackProvider,
        NoOpVisionProvider,
        OpenAICompatibleVisionProvider,
        GenflowAiVisionProvider,
        OllamaVisionProvider,
    )

    storage_dir = Path(
        os.environ.get("MULTIMODAL_STORAGE_DIR", "/app/agent/data/multimodal")
    )
    db_path = Path(
        os.environ.get("VIBE_TRADING_DB_PATH", "/app/agent/data/vibe_trading.db")
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
