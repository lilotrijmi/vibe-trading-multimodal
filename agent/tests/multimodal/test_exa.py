"""Tests for the Exa search and content client."""

from __future__ import annotations

import json
from unittest.mock import patch

import httpx
import pytest

from src.multimodal.exa import (
    ExaClient,
    ExaError,
    ExaSearchResult,
    ExaContent,
    format_contents_as_text,
    format_search_results_as_text,
)


@pytest.fixture(autouse=True)
def _clear_exa_env(monkeypatch):
    """Ensure EXA_API_KEY is not set from the host environment during tests."""
    monkeypatch.delenv("EXA_API_KEY", raising=False)
    monkeypatch.delenv("EXA_BASE_URL", raising=False)
    monkeypatch.delenv("EXA_MAX_RESULTS", raising=False)


@pytest.fixture
def client() -> ExaClient:
    return ExaClient(api_key="test-key", base_url="https://exa.example.com")


def test_is_configured_with_key() -> None:
    c = ExaClient(api_key="abc")
    assert c.is_configured is True


def test_is_configured_without_key() -> None:
    c = ExaClient(api_key="")
    assert c.is_configured is False


def test_search_sends_post_and_parses_results() -> None:
    captured = {}

    async def fake_post(self, url, json=None, headers=None):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "title": "COTI news",
                        "url": "https://example.com/coti",
                        "text": "COTI price up",
                        "publishedDate": "2026-07-29",
                        "author": "Reporter",
                        "score": 0.9,
                    },
                    {
                        "title": "COTI analysis",
                        "url": "https://example.com/coti2",
                        "text": "Technical indicators",
                    },
                ]
            },
        )

    with patch.object(httpx.AsyncClient, "post", new=fake_post):
        c = ExaClient(api_key="k", base_url="https://x.test")
        results = _async_runner(c.search, "COTI")

    assert captured["url"] == "https://x.test/search"
    assert captured["json"]["query"] == "COTI"
    assert captured["json"]["numResults"] == 5
    assert captured["headers"]["x-api-key"] == "k"
    assert len(results) == 2
    assert results[0].title == "COTI news"
    assert results[0].url == "https://example.com/coti"
    assert results[0].snippet == "COTI price up"
    assert results[1].author is None


def test_search_raises_on_http_error() -> None:
    async def fake_post(self, url, json=None, headers=None):
        return httpx.Response(403, text="Forbidden")

    with patch.object(httpx.AsyncClient, "post", new=fake_post):
        c = ExaClient(api_key="k", base_url="https://x.test")
        with pytest.raises(ExaError, match="403"):
            _async_runner(c.search, "x")


def test_get_contents_truncates_to_10() -> None:
    captured = {}

    async def fake_post(self, url, json=None, headers=None):
        captured["json"] = json
        return httpx.Response(200, json={"results": []})

    urls = [f"https://example.com/{i}" for i in range(20)]
    with patch.object(httpx.AsyncClient, "post", new=fake_post):
        c = ExaClient(api_key="k")
        _async_runner(c.get_contents, urls)

    assert len(captured["json"]["ids"]) == 10


def test_get_contents_raises_on_http_error() -> None:
    async def fake_post(self, url, json=None, headers=None):
        return httpx.Response(500, text="server error")

    with patch.object(httpx.AsyncClient, "post", new=fake_post):
        c = ExaClient(api_key="k")
        with pytest.raises(ExaError, match="500"):
            _async_runner(c.get_contents, ["https://x"])


def test_search_raises_when_no_key() -> None:
    c = ExaClient(api_key="")
    with pytest.raises(ExaError, match="not configured"):
        _async_runner(c.search, "x")


def test_format_search_results_renders_block() -> None:
    results = [
        ExaSearchResult(
            title="T1",
            url="https://x.com",
            snippet="snippet 1",
            published_date="2026-07-29",
            author="A",
            score=0.9,
        )
    ]
    text = format_search_results_as_text(results)
    assert "T1" in text
    assert "https://x.com" in text
    assert "published: 2026-07-29" in text


def test_format_search_results_empty() -> None:
    assert format_search_results_as_text([]) == ""


def test_format_contents_renders_block() -> None:
    contents = [
        ExaContent(
            url="https://x.com",
            title="Title",
            text="body text",
            summary="summary text",
        )
    ]
    text = format_contents_as_text(contents)
    assert "Title" in text
    assert "body text" in text
    assert "summary text" in text


# Helper to drive async methods in sync tests.
def _async_runner(coro_func, *args, **kwargs):
    """Run an async coroutine and return the result synchronously."""
    import asyncio

    return asyncio.new_event_loop().run_until_complete(coro_func(*args, **kwargs))
