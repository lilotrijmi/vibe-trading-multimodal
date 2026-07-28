from __future__ import annotations

from src.multimodal.input_classifier import (
    Attachment,
    AttachmentType,
    InputClassifier,
)


def test_classify_http_url() -> None:
    classifier = InputClassifier()
    result = classifier.classify("https://example.com/article")
    assert result.type == AttachmentType.URL
    assert result.source == "https://example.com/article"


def test_classify_local_path() -> None:
    classifier = InputClassifier()
    result = classifier.classify("/tmp/chart.png")
    assert result.type == AttachmentType.PATH
    assert result.source == "/tmp/chart.png"


def test_classify_data_uri() -> None:
    classifier = InputClassifier()
    result = classifier.classify("data:image/png;base64,iVBORw0KG...")
    assert result.type == AttachmentType.IMAGE_DATA_URI


def test_classify_text_input() -> None:
    classifier = InputClassifier()
    result = classifier.classify("just some text")
    assert result.type == AttachmentType.TEXT
