from __future__ import annotations

from unittest.mock import MagicMock

from src.multimodal.tools import (
    MultimodalToolRegistry,
    describe_image,
    url_read,
)


def test_url_read_returns_sanitized_content() -> None:
    fetcher = MagicMock()
    fetcher.fetch.return_value = MagicMock(
        url="https://example.com",
        final_url="https://example.com",
        text="raw text",
        title="T",
        status=200,
    )
    sanitizer = MagicMock()
    sanitizer.sanitize.return_value = MagicMock(
        text="sanitized",
        source_url="https://example.com",
        was_truncated=False,
    )

    result = url_read(
        url="https://example.com",
        fetcher=fetcher,
        sanitizer=sanitizer,
    )
    assert result == "sanitized"
    fetcher.fetch.assert_called_once_with("https://example.com")


def test_describe_image_uses_vision_provider() -> None:
    vision = MagicMock()
    vision.analyze.return_value = MagicMock(description="chart description", provider="openai")

    result = describe_image(
        image_bytes=b"abc",
        prompt="describe",
        vision_provider=vision,
    )
    assert "chart description" in result
    vision.analyze.assert_called_once_with(b"abc", "describe")




def test_registry_returns_both_tools() -> None:
    registry = MultimodalToolRegistry()
    tools = registry.list_tools()
    assert "url_read" in tools
    assert "describe_image" in tools


def test_url_read_returns_generic_error_when_sanitization_fails() -> None:
    fetcher = MagicMock()
    fetcher.fetch.return_value = MagicMock(
        text="raw text",
        final_url="https://example.com",
    )
    sanitizer = MagicMock()
    sanitizer.sanitize.side_effect = RuntimeError("secret-internal-path")

    result = url_read(
        url="https://example.com",
        fetcher=fetcher,
        sanitizer=sanitizer,
    )

    assert result == "Error: unable to fetch and sanitize URL content."
    assert "secret-internal-path" not in result


def test_url_read_records_and_blocks_burst() -> None:
    fetcher = MagicMock()
    sanitizer = MagicMock()
    abuse = MagicMock()
    abuse.snapshot.return_value = MagicMock(is_burst=True)

    result = url_read(
        url="https://example.com",
        fetcher=fetcher,
        sanitizer=sanitizer,
        abuse=abuse,
    )

    assert result == "Error: URL fetch rate limit exceeded."
    abuse.record.assert_called_once_with("https://example.com")
    fetcher.fetch.assert_not_called()


def test_describe_image_does_not_expose_provider_error() -> None:
    vision = MagicMock()
    vision.analyze.side_effect = RuntimeError("secret-provider-detail")

    result = describe_image(
        image_bytes=b"abc",
        prompt="describe",
        vision_provider=vision,
    )

    assert result == "Error: unable to analyze image."
    assert "secret-provider-detail" not in result
