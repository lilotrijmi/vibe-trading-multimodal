"""API routes for multimodal attachments."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.api.models import UploadResponse
from src.db.models import Conversation, Message
from src.db.session import get_session
from src.multimodal.context_packer import AttachmentContext, ContextPacker
from src.multimodal.exceptions import InputValidationError
from src.multimodal.image_pipeline import ImagePipeline
from src.multimodal.url_reader import URLContentSanitizer
from src.multimodal.exa import (
    ExaClient,
    ExaError,
    format_contents_as_text,
    format_search_results_as_text,
)
from src.multimodal.vision_provider import VisionProvider

logger = logging.getLogger(__name__)


async def _call_llm_with_context(prompt: str) -> str:
    """Call the agent's LLM (OpenAI-compatible) with the multimodal context.

    Reads ``OPENAI_API_KEY`` / ``OPENAI_BASE_URL`` / ``LANGCHAIN_MODEL_NAME`` from
    environment. Falls back to ``OPENROUTER_*`` if OpenAI key is absent. Auto-
    detects Genflow-style keys (``gf-`` prefix) and routes to the Genflow
    endpoint when no ``OPENAI_BASE_URL`` is configured. Any failure raises so
    the caller can show a context-only fallback to the user.
    """
    api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("OPENROUTER_API_KEY")
    base_url = (
        os.environ.get("OPENAI_BASE_URL")
        or os.environ.get("OPENROUTER_BASE_URL")
    )
    # Auto-detect Genflow API key (starts with "gf-") and route to Genflow
    # endpoint when no explicit base URL is set. This avoids the 401 that
    # occurs when a Genflow key is sent to api.openai.com.
    if not base_url and api_key and api_key.startswith("gf-"):
        base_url = "https://v1.genflow.id/v1"
    if not base_url:
        base_url = "https://api.openai.com/v1"

    model = os.environ.get("LANGCHAIN_MODEL_NAME", "gpt-4o-mini")
    if not api_key:
        raise RuntimeError(
            "no LLM API key configured (set OPENAI_API_KEY or OPENROUTER_API_KEY)"
        )

    from langchain_openai import ChatOpenAI

    llm = ChatOpenAI(model=model, api_key=api_key, base_url=base_url, temperature=0.3)
    response = await llm.ainvoke(prompt)
    return response.content if hasattr(response, "content") else str(response)


def _get_active_vision_provider() -> Any:
    """Return the vision provider, lazily rebuilt from runtime env.

    Settings can change the VISION_* env vars without restarting the server;
    this helper rebuilds the provider on each chat call so changes apply
    immediately. Returns ``None`` if vision is disabled or unconfigured.
    """
    if os.environ.get("VISION_ENABLED", "true").lower() in ("false", "0", "no"):
        logger.info("vision: VISION_ENABLED=false, skipping")
        return None
    api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        logger.info("vision: no API key in env (OPENAI_API_KEY/ANTHROPIC_API_KEY)")
        return None

    try:
        from src.multimodal.vision_provider import (
            NoOpVisionProvider,
            OpenAICompatibleVisionProvider,
            GenflowAiVisionProvider,
            OllamaVisionProvider,
        )
        from langchain_openai import ChatOpenAI
    except ImportError as exc:
        logger.warning("vision: imports failed: %s", exc)
        return None

    vision_model = os.environ.get("VISION_MODEL", "gpt-4o")
    base_url = (
        os.environ.get("OPENAI_BASE_URL")
        or os.environ.get("ANTHROPIC_BASE_URL")
        or "https://api.openai.com/v1"
    )

    # Auto-detect Genflow
    if api_key.startswith("gf-") and not os.environ.get("OPENAI_BASE_URL"):
        base_url = "https://v1.genflow.id/v1"

    provider_name = os.environ.get("VISION_PROVIDER", "openai").lower()
    logger.info(
        "vision build: provider=%s model=%s base_url=%s key_prefix=%s",
        provider_name, vision_model, base_url, api_key[:4] + "***",
    )

    if provider_name in (
        "openai",
        "gpt-4o",
        "gpt-4-vision",
        "genflow",  # Genflow API is OpenAI-compatible
        "minimax",  # Common alias for custom OpenAI-compatible gateways
    ):
        return OpenAICompatibleVisionProvider(
            client=ChatOpenAI(model=vision_model, api_key=api_key, base_url=base_url),
            model=vision_model,
        )
    if provider_name in ("anthropic", "claude"):
        return GenflowAiVisionProvider(
            client=_build_Anthropic_client(vision_model, api_key),
            model=vision_model,
        )
    if provider_name == "ollama":
        return OllamaVisionProvider(
            client=_build_ollama_client(),
            model=vision_model,
            host=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434"),
        )
    logger.warning("vision: unknown provider %r, returning NoOp", provider_name)
    return NoOpVisionProvider()


def _build_Anthropic_client(model: str, api_key: str) -> Any:
    """Lazy Anthropic client builder. Returns None if package missing."""
    try:
        from langchain_community.chat_models import ChatAnthropic
    except ImportError:
        return None
    return ChatAnthropic(
        model=model,
        anthropic_api_key=api_key,
    )


def _build_ollama_client() -> Any:
    """Lazy Ollama client builder."""
    try:
        import ollama
    except ImportError:
        return None
    return ollama.Client(host=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434"))


router = APIRouter(prefix="/api/multimodal", tags=["multimodal"])


@dataclass
class MultimodalState:
    """Runtime state for multimodal integration."""

    vision_provider: VisionProvider | None = None
    url_reader: Any = None
    content_sanitizer: URLContentSanitizer | None = None


_state = MultimodalState()


def configure(pipeline: ImagePipeline, storage_dir: Any) -> None:
    """Configure image pipeline and storage."""
    global _IMAGE_PIPELINE, _MULTIMODAL_DIR
    _IMAGE_PIPELINE = pipeline
    _MULTIMODAL_DIR = storage_dir
    if storage_dir is not None:
        storage_dir.mkdir(parents=True, exist_ok=True)


def configure_integration(
    vision_provider: VisionProvider | None = None,
    url_reader: Any = None,
    content_sanitizer: URLContentSanitizer | None = None,
) -> None:
    """Configure integration with vision/URL components."""
    _state.vision_provider = vision_provider
    _state.url_reader = url_reader
    _state.content_sanitizer = content_sanitizer


_IMAGE_PIPELINE: ImagePipeline | None = None
_MULTIMODAL_DIR: Any = None


def _get_pipeline() -> ImagePipeline:
    if _IMAGE_PIPELINE is None:
        raise HTTPException(status_code=503, detail="image pipeline not configured")
    return _IMAGE_PIPELINE


def _get_storage() -> Any:
    if _MULTIMODAL_DIR is None:
        raise HTTPException(status_code=503, detail="storage not configured")
    return _MULTIMODAL_DIR


def _db() -> Session:
    return get_session()


@router.post("/upload", response_model=UploadResponse)
async def upload_image(
    request: Request,
    file: UploadFile = File(...),
    session: Session = Depends(_db),
) -> UploadResponse:
    """Upload an image and return metadata."""
    pipeline = _get_pipeline()
    storage = _get_storage()
    raw = await file.read()
    try:
        result = pipeline.process(raw, content_type=file.content_type or "application/octet-stream")
    except InputValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    from datetime import datetime, timedelta, timezone

    expires_at = datetime.now(timezone.utc) + timedelta(days=30)
    file_path = storage / f"{result.bytes_hash}.png"
    file_path.write_bytes(result.persisted_bytes)

    from src.db.models import Attachment

    attachment = Attachment(
        message_id=0,
        type="image",
        source=file.filename or "uploaded.png",
        mime=result.mime,
        size_bytes=len(result.persisted_bytes),
        bytes_hash=result.bytes_hash,
        expires_at=expires_at,
    )
    session.add(attachment)
    session.commit()
    session.refresh(attachment)

    return UploadResponse(
        attachment_id=attachment.id,
        bytes_hash=result.bytes_hash,
        mime=result.mime,
        width=result.width,
        height=result.height,
        expires_at=expires_at.isoformat(),
    )


@router.post("/chat")
async def chat(
    request: Request,
    text: str = Form(""),
    urls: str = Form(""),
    image: UploadFile = File(None),
    session: Session = Depends(_db),
) -> dict[str, Any]:
    """Chat endpoint that accepts text, URLs, and an image."""
    url_list = [u.strip() for u in urls.split(",") if u.strip()]

    conv = session.query(Conversation).first()
    if conv is None:
        conv = Conversation(title="Chat")
        session.add(conv)
        session.flush()

    image_descriptions = []
    if image is not None:
        raw = await image.read()
        try:
            img_result = _get_pipeline().process(
                raw, content_type=image.content_type or ""
            )
        except InputValidationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        # Prefer the in-process provider set via configure_integration (used in
        # tests + during startup). Fall back to a lazy provider built from the
        # current env so Settings UI changes take effect without a restart.
        state_vision = _state.vision_provider
        is_noop = state_vision is not None and type(state_vision).__name__ == "NoOpVisionProvider"
        env_vision = None if (state_vision and not is_noop) else _get_active_vision_provider()
        vision = state_vision if state_vision and not is_noop else env_vision
        logger.info(
            "vision selected: %s (state=%s, env=%s, enabled=%s, key=%s)",
            type(vision).__name__ if vision else "None",
            type(state_vision).__name__ if state_vision else "None",
            type(env_vision).__name__ if env_vision else "None",
            os.environ.get("VISION_ENABLED", "true"),
            "set" if (os.environ.get("OPENAI_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")) else "missing",
        )
        if vision is not None:
            try:
                vision_result = vision.analyze(
                    img_result.persisted_bytes,
                    "Describe this chart or image for trading analysis. "
                    "Include any visible numbers, indicators, support/resistance "
                    "levels, and trend direction.",
                )
                logger.info(
                    "vision success: provider=%s desc_len=%d",
                    vision_result.provider,
                    len(vision_result.description or ""),
                )
                image_descriptions.append(
                    AttachmentContext(
                        type="image",
                        source=image.filename or "uploaded.png",
                        content=vision_result.description or "(no description returned)",
                    )
                )
            except Exception as exc:
                logger.warning("vision provider failed: %s", exc)
                image_descriptions.append(
                    AttachmentContext(
                        type="image",
                        source=image.filename or "uploaded.png",
                        content=f"(vision failed: {exc})",
                    )
                )

    url_contents = []
    for url in url_list:
        if _state.url_reader is None or _state.content_sanitizer is None:
            break
        try:
            fetch_result = _state.url_reader.fetch(url)
        except Exception as exc:
            url_contents.append(
                AttachmentContext(
                    type="url",
                    source=url,
                    content=f"(fetch failed: {exc})",
                )
            )
            continue
        sanitized = _state.content_sanitizer.sanitize(
            fetch_result.text, source_url=fetch_result.final_url
        )
        url_contents.append(
            AttachmentContext(
                type="url",
                source=url,
                content=sanitized.text,
            )
        )

    packer = ContextPacker()
    ctx = packer.build(
        user_text=text,
        image_descriptions=image_descriptions,
        url_contents=url_contents,
    )

    # Persist the original user message; the assistant response is generated
    # downstream by the regular agent service (``/sessions/{id}/messages``)
    # so the answer benefits from skills, swarm, tools, and language detection.
    msg = Message(conversation_id=conv.id, role="user", content=text)
    session.add(msg)
    session.flush()
    session.commit()

    # Return the packed prompt — the frontend feeds this into the regular
    # agent loop. No LLM call here.
    return {
        "message_id": msg.id,
        "conversation_id": conv.id,
        "prompt": ctx.full_prompt,
    }


# ---------------------------------------------------------------------------
# Exa web search + content fetch
# ---------------------------------------------------------------------------


class ExaSearchRequest(BaseModel):
    """Run a web search via Exa."""

    query: str = Field(..., min_length=1, max_length=2000)
    num_results: int = Field(5, ge=1, le=20)
    include_domains: list[str] | None = None
    api_key: str | None = None  # Optional override for the runtime API key


class ExaSearchResponse(BaseModel):
    """Search results + the rendered text block for LLM context."""

    results: list[dict[str, Any]]
    context: str  # Plain-text block ready to feed the LLM.


class ExaContentsRequest(BaseModel):
    """Fetch clean content of one or more URLs via Exa (anti-bot fallback)."""

    urls: list[str] = Field(..., min_length=1, max_length=10)
    summary: bool = False
    api_key: str | None = None


class ExaContentsResponse(BaseModel):
    """Exa contents + the rendered text block."""

    contents: list[dict[str, Any]]
    context: str


class ExaSettingsResponse(BaseModel):
    """Current Exa configuration state for the Settings UI."""

    api_key_configured: bool
    api_key_hint: str | None = None
    base_url: str
    max_results: int
    enabled: bool
    env_path: str | None = None


def _get_exa_client(api_key: str | None = None) -> ExaClient:
    """Return an ExaClient honoring the API key override or runtime env."""
    return ExaClient(api_key=api_key)


@router.get("/exa/settings", response_model=ExaSettingsResponse)
async def get_exa_settings() -> ExaSettingsResponse:
    """Return Exa configuration for the Settings UI."""
    client = _get_exa_client()
    return ExaSettingsResponse(
        api_key_configured=client.is_configured,
        api_key_hint=None,
        base_url=client._base_url,
        max_results=client._max_results,
        enabled=os.environ.get("EXA_ENABLED", "true").lower() not in ("false", "0", "no"),
        env_path=None,
    )


@router.post("/exa/search", response_model=ExaSearchResponse)
async def exa_search(payload: ExaSearchRequest) -> ExaSearchResponse:
    """Run a web search via Exa and return results + LLM-ready context text."""
    client = _get_exa_client(api_key=payload.api_key)
    if not client.is_configured:
        raise HTTPException(
            status_code=503,
            detail="Exa is not configured. Set EXA_API_KEY in the environment or Settings.",
        )
    try:
        results = await client.search(
            payload.query,
            num_results=payload.num_results,
            include_domains=payload.include_domains,
        )
    except ExaError as exc:
        raise HTTPException(status_code=502, detail=f"Exa error: {exc}") from exc

    results_dicts = [
        {
            "title": r.title,
            "url": r.url,
            "snippet": r.snippet,
            "published_date": r.published_date,
            "author": r.author,
            "score": r.score,
        }
        for r in results
    ]
    return ExaSearchResponse(
        results=results_dicts,
        context=format_search_results_as_text(results),
    )


@router.post("/exa/contents", response_model=ExaContentsResponse)
async def exa_contents(payload: ExaContentsRequest) -> ExaContentsResponse:
    """Fetch clean markdown content of one or more URLs via Exa (anti-bot fallback)."""
    client = _get_exa_client(api_key=payload.api_key)
    if not client.is_configured:
        raise HTTPException(
            status_code=503,
            detail="Exa is not configured. Set EXA_API_KEY in the environment or Settings.",
        )
    try:
        contents = await client.get_contents(
            payload.urls,
            summary=payload.summary,
        )
    except ExaError as exc:
        raise HTTPException(status_code=502, detail=f"Exa error: {exc}") from exc

    contents_dicts = [
        {
            "url": c.url,
            "title": c.title,
            "text": c.text,
            "summary": c.summary,
        }
        for c in contents
    ]
    return ExaContentsResponse(
        contents=contents_dicts,
        context=format_contents_as_text(contents),
    )
