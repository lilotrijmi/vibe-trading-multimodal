"""API routes for multimodal attachments."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from src.api.models import UploadResponse
from src.db.models import Conversation, Message
from src.db.session import get_session
from src.multimodal.context_packer import AttachmentContext, ContextPacker
from src.multimodal.exceptions import InputValidationError
from src.multimodal.image_pipeline import ImagePipeline
from src.multimodal.url_reader import URLContentSanitizer
from src.multimodal.vision_provider import VisionProvider

logger = logging.getLogger(__name__)


async def _call_llm_with_context(prompt: str) -> str:
    """Call the agent's LLM (OpenAI-compatible) with the multimodal context.

    Reads ``OPENAI_API_KEY`` / ``OPENAI_BASE_URL`` / ``LANGCHAIN_MODEL_NAME`` from
    environment. Falls back to ``OPENROUTER_*`` if OpenAI key is absent. Any
    failure raises so the caller can show a context-only fallback to the user.
    """
    api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("OPENROUTER_API_KEY")
    base_url = os.environ.get("OPENAI_BASE_URL") or os.environ.get(
        "OPENROUTER_BASE_URL", "https://api.openai.com/v1"
    )
    model = os.environ.get("LANGCHAIN_MODEL_NAME", "gpt-4o-mini")
    if not api_key:
        raise RuntimeError(
            "no LLM API key configured (set OPENAI_API_KEY or OPENROUTER_API_KEY)"
        )

    from langchain_openai import ChatOpenAI

    llm = ChatOpenAI(model=model, api_key=api_key, base_url=base_url, temperature=0.3)
    response = await llm.ainvoke(prompt)
    return response.content if hasattr(response, "content") else str(response)

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
    text: str = "",
    urls: str = "",
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
        if _state.vision_provider is not None:
            try:
                vision_result = _state.vision_provider.analyze(
                    img_result.persisted_bytes,
                    "Describe this chart or image for trading analysis.",
                )
                image_descriptions.append(
                    AttachmentContext(
                        type="image",
                        source=image.filename or "uploaded.png",
                        content=vision_result.description,
                    )
                )
            except Exception as exc:
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

    msg = Message(conversation_id=conv.id, role="user", content=text)
    session.add(msg)
    session.flush()

    # Call the agent's LLM with the packed multimodal context.
    # Falls back to a context summary if the LLM call fails (e.g. provider
    # misconfigured, network error, vision not supported by current model).
    try:
        response_text = await _call_llm_with_context(ctx.full_prompt)
    except Exception as exc:
        logger.warning("LLM call failed, returning context summary: %s", exc)
        response_text = (
            f"[trading analysis] (LLM unavailable: {exc})\n\n"
            f"Vision/URL context:\n{ctx.full_prompt[:2000]}"
        )

    assistant_msg = Message(conversation_id=conv.id, role="assistant", content=response_text)
    session.add(assistant_msg)
    session.commit()

    return {"message_id": msg.id, "response": response_text}
