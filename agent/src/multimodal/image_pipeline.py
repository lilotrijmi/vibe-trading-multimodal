"""Image pipeline for validation, resizing, hashing, and storage."""

from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from src.multimodal.exceptions import ImageProcessingError, InputValidationError

__all__ = ["ImagePipeline", "ImageProcessingError", "ProcessedImage"]

_ALLOWED_MIME = frozenset({"image/png", "image/jpeg", "image/webp", "image/gif"})


@dataclass(frozen=True)
class ProcessedImage:
    """Result of image processing."""

    bytes_hash: str
    mime: str
    width: int
    height: int
    persisted_bytes: bytes
    persisted_path: Path | None


class _LocalStorage:
    """Simple filesystem-based storage for deduplication."""

    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir

    def has(self, hash_val: str) -> bool:
        return (self.base_dir / hash_val).exists()

    def put(self, hash_val: str, data: bytes) -> Path:
        path = self.base_dir / hash_val
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path


class ImagePipeline:
    """Validates, resizes, hashes, and stores uploaded images."""

    def __init__(
        self,
        max_bytes: int = 25_000_000,
        max_dimension: int = 2048,
        storage: _LocalStorage | None = None,
    ) -> None:
        self._max_bytes = max_bytes
        self._max_dimension = max_dimension
        self._storage = storage

    def process(self, raw: bytes, content_type: str) -> ProcessedImage:
        if content_type not in _ALLOWED_MIME:
            raise InputValidationError(f"unsupported content-type: {content_type!r}")

        if len(raw) > self._max_bytes:
            raise InputValidationError(
                f"image too large: {len(raw)} bytes (max {self._max_bytes})"
            )

        try:
            img = Image.open(io.BytesIO(raw))
            img.verify()
        except Exception as exc:
            raise InputValidationError(f"invalid image data: {exc}") from exc

        # Reopen for resize (verify() invalidates the image)
        img = Image.open(io.BytesIO(raw))
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGB")

        # Resize if too large
        if max(img.size) > self._max_dimension:
            img.thumbnail((self._max_dimension, self._max_dimension), Image.LANCZOS)

        # Encode back to PNG
        out = io.BytesIO()
        img.save(out, format="PNG")
        out_bytes = out.getvalue()

        # Hash
        hash_val = hashlib.sha256(out_bytes).hexdigest()

        # Persist
        persisted_path: Path | None = None
        if self._storage is not None:
            if not self._storage.has(hash_val):
                persisted_path = self._storage.put(hash_val, out_bytes)

        return ProcessedImage(
            bytes_hash=hash_val,
            mime="image/png",
            width=img.size[0],
            height=img.size[1],
            persisted_bytes=out_bytes,
            persisted_path=persisted_path,
        )
