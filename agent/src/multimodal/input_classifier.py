"""Classifies user input as text, URL, path, or image."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from urllib.parse import urlparse


class AttachmentType(str, Enum):
    TEXT = "text"
    URL = "url"
    PATH = "path"
    IMAGE_DATA_URI = "image_data_uri"


@dataclass(frozen=True)
class Attachment:
    """Classified attachment input."""

    type: AttachmentType
    source: str


class InputClassifier:
    """Detects input type from raw user content."""

    def classify(self, content: str) -> Attachment:
        stripped = content.strip()
        if not stripped:
            return Attachment(type=AttachmentType.TEXT, source="")

        if stripped.startswith("data:image/"):
            return Attachment(type=AttachmentType.IMAGE_DATA_URI, source=stripped)

        parsed = urlparse(stripped)
        if parsed.scheme in ("http", "https") and parsed.netloc:
            return Attachment(type=AttachmentType.URL, source=stripped)

        if (
            stripped.startswith("/")
            or stripped.startswith("./")
            or stripped.startswith("../")
            or (len(stripped) > 2 and stripped[1] == ":")
        ):
            return Attachment(type=AttachmentType.PATH, source=stripped)

        return Attachment(type=AttachmentType.TEXT, source=stripped)
