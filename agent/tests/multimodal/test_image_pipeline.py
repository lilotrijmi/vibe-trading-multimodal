from __future__ import annotations

import io

import pytest
from PIL import Image

from src.multimodal.image_pipeline import ImagePipeline
from src.multimodal.exceptions import InputValidationError


def _make_png_bytes(size: tuple[int, int] = (100, 100), color: str = "red") -> bytes:
    img = Image.new("RGB", size, color=color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_pipeline_validates_png_mime() -> None:
    pipeline = ImagePipeline(max_bytes=10_000_000)
    png = _make_png_bytes()
    result = pipeline.process(png, content_type="image/png")
    assert result.mime == "image/png"
    assert result.bytes_hash
    assert len(result.persisted_bytes) > 0


def test_pipeline_rejects_non_image() -> None:
    pipeline = ImagePipeline(max_bytes=10_000_000)
    with pytest.raises(InputValidationError):
        pipeline.process(b"not an image", content_type="text/plain")


def test_pipeline_rejects_oversized() -> None:
    pipeline = ImagePipeline(max_bytes=1000)
    png = _make_png_bytes((2000, 2000))
    with pytest.raises(InputValidationError):
        pipeline.process(png, content_type="image/png")


def test_pipeline_resizes_large_image() -> None:
    pipeline = ImagePipeline(max_bytes=10_000_000, max_dimension=512)
    png = _make_png_bytes((2000, 2000))
    result = pipeline.process(png, content_type="image/png")
    img = Image.open(io.BytesIO(result.persisted_bytes))
    assert max(img.size) <= 512


def test_pipeline_dedupe_by_hash() -> None:
    pipeline = ImagePipeline(max_bytes=10_000_000)

    class FakeStorage:
        def __init__(self):
            self.seen: dict[str, bytes] = {}

        def has(self, h: str) -> bool:
            return h in self.seen

        def put(self, h: str, data: bytes) -> None:
            self.seen[h] = data

    storage = FakeStorage()
    pipeline._storage = storage  # type: ignore[attr-defined]

    png = _make_png_bytes()
    r1 = pipeline.process(png, content_type="image/png")
    r2 = pipeline.process(png, content_type="image/png")
    assert r1.bytes_hash == r2.bytes_hash
    assert len(storage.seen) == 1
