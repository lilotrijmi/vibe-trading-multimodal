"""Smoke test: ensure all multimodal imports succeed after a clean install.

Run via: pytest tools/test_multimodal_imports.py -q
or:     python -c "import tools.test_multimodal_imports"
"""

from __future__ import annotations

import importlib
import sys

import pytest


REQUIRED_MODULES = [
    # Core multimodal stack
    "src.multimodal",
    "src.multimodal.vision_provider",
    "src.multimodal.url_reader",
    "src.multimodal.image_pipeline",
    "src.multimodal.input_classifier",
    "src.multimodal.context_packer",
    "src.multimodal.summarizer",
    "src.multimodal.abuse_detector",
    "src.multimodal.tools",
    "src.multimodal.exceptions",
    # DB layer
    "src.db",
    "src.db.models",
    "src.db.session",
    # API integration
    "src.api.multimodal_routes",
    "src.api.multimodal_startup",
    # Third-party deps
    "sqlalchemy",
    "PIL",  # Pillow
    "httpx",
    "trafilatura",
    "bleach",
]


@pytest.mark.parametrize("module_name", REQUIRED_MODULES)
def test_module_imports(module_name: str) -> None:
    """Each module must import without raising."""
    if module_name in sys.modules:
        importlib.reload(sys.modules[module_name])
    else:
        importlib.import_module(module_name)


def test_sqlalchemy_session_class_available() -> None:
    """sqlalchemy.orm.Session must be importable."""
    from sqlalchemy.orm import Session

    assert Session is not None


def test_fastapi_app_loads() -> None:
    """Top-level FastAPI app must import successfully."""
    from api_server import app

    assert app is not None
    assert len(app.routes) > 0
