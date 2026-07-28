from __future__ import annotations

import io
import os
from pathlib import Path

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
    yield TestClient(app)
    # reset state
    configure(pipeline=ImagePipeline(), storage_dir=None)


def test_upload_image_returns_attachment_id(client: TestClient) -> None:
    from PIL import Image
    img = Image.new("RGB", (100, 100), color="red")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    response = client.post(
        "/api/multimodal/upload",
        files={"file": ("test.png", buf, "image/png")},
    )
    assert response.status_code == 200
    body = response.json()
    assert "attachment_id" in body
    assert body["mime"] == "image/png"


def test_upload_rejects_non_image(client: TestClient) -> None:
    response = client.post(
        "/api/multimodal/upload",
        files={"file": ("test.txt", io.BytesIO(b"not an image"), "text/plain")},
    )
    assert response.status_code == 400
