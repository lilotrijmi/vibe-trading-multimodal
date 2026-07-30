from __future__ import annotations

import io
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.multimodal_routes import (
    configure,
    configure_integration,
    router,
)
from src.db.session import init_db
from src.multimodal.image_pipeline import ImagePipeline
from src.multimodal.url_reader import URLContentSanitizer
from src.multimodal.vision_provider import VisionProvider, VisionResult


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    db_path = tmp_path / "test.db"
    storage_dir = tmp_path / "storage"
    init_db(db_path)
    app = FastAPI()
    app.include_router(router)
    configure(pipeline=ImagePipeline(), storage_dir=storage_dir)
    configure_integration(
        vision_provider=None,
        url_reader=None,
        content_sanitizer=URLContentSanitizer(),
    )
    yield TestClient(app)


def test_chat_endpoint_accepts_text_only(client: TestClient) -> None:
    response = client.post(
        "/api/multimodal/chat",
        data={"text": "what is the trend on AAPL?"},
    )
    assert response.status_code == 200
    body = response.json()
    assert "message_id" in body
    assert "prompt" in body
    # The packed prompt should contain the user's question for the agent loop
    # to consume downstream.
    assert "what is the trend on AAPL?" in body["prompt"]


def test_chat_endpoint_accepts_url(client: TestClient) -> None:
    from src.multimodal.url_reader import URLContentSanitizer, FetchResult

    fake_reader = MagicMock()
    fake_reader.fetch.return_value = FetchResult(
        url="https://example.com",
        final_url="https://example.com",
        text="some text",
        title="T",
        status=200,
    )
    configure_integration(
        url_reader=fake_reader,
        content_sanitizer=URLContentSanitizer(),
    )
    response = client.post(
        "/api/multimodal/chat",
        data={"text": "summarize", "urls": "https://example.com"},
    )
    assert response.status_code == 200


def test_chat_endpoint_accepts_image(client: TestClient) -> None:
    from PIL import Image
    img = Image.new("RGB", (100, 100), color="red")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    class FakeVision(VisionProvider):
        def analyze(self, image_bytes, prompt):
            return VisionResult(description="chart: uptrend", provider="fake")

    configure_integration(vision_provider=FakeVision())
    response = client.post(
        "/api/multimodal/chat",
        data={"text": "analyze chart"},
        files={"image": ("chart.png", buf, "image/png")},
    )
    assert response.status_code == 200
    body = response.json()
    # The packed prompt should embed the vision description so the regular
    # agent service can answer with the full multimodal context.
    assert "chart: uptrend" in body["prompt"]
