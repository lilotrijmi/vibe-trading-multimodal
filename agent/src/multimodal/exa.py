"""Exa search and content extraction client.

Exa (https://exa.ai) is a web search and content extraction API designed for
AI agents. We use it to:

  1. Search the web for current news/articles on a given query.
  2. Fetch the clean markdown content of a specific URL as a fallback when
     the direct HTTP fetch fails (e.g. 403 Forbidden, anti-bot wall).

Configuration is read from environment variables (preferred) or from runtime
state set via the Settings UI.

Env vars:
  EXA_API_KEY          Required. Exa API key.
  EXA_BASE_URL         Optional. Override the default endpoint.
  EXA_MAX_RESULTS      Optional. Max search results (default 5).
  EXA_ENABLED          Optional. "true"/"false" (default true when key set).
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://api.exa.ai"
DEFAULT_MAX_RESULTS = 5


@dataclass(frozen=True)
class ExaSearchResult:
    """A single Exa search result."""

    title: str
    url: str
    snippet: str
    published_date: str | None = None
    author: str | None = None
    score: float | None = None


@dataclass(frozen=True)
class ExaContent:
    """Content extracted from a URL via Exa."""

    url: str
    title: str | None
    text: str
    summary: str | None = None


class ExaError(RuntimeError):
    """Raised when the Exa API returns an error or is misconfigured."""


class ExaClient:
    """Thin async-friendly wrapper around the Exa REST API."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        max_results: int | None = None,
    ) -> None:
        self._api_key = api_key or os.environ.get("EXA_API_KEY", "")
        self._base_url = (base_url or os.environ.get("EXA_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
        self._max_results = max_results or int(os.environ.get("EXA_MAX_RESULTS", str(DEFAULT_MAX_RESULTS)))

    @property
    def is_configured(self) -> bool:
        """Return True if an API key is available."""
        return bool(self._api_key)

    def _headers(self) -> dict[str, str]:
        if not self._api_key:
            raise ExaError("EXA_API_KEY not configured")
        return {
            "x-api-key": self._api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def search(
        self,
        query: str,
        *,
        num_results: int | None = None,
        include_domains: list[str] | None = None,
        use_autoprompt: bool = True,
    ) -> list[ExaSearchResult]:
        """Run a web search and return a list of results.

        Args:
            query: Search query (natural language).
            num_results: Number of results (defaults to ``EXA_MAX_RESULTS``).
            include_domains: Restrict to a list of domains (optional).
            use_autoprompt: Let Exa optimize the query (recommended).
        """
        payload: dict[str, Any] = {
            "query": query,
            "numResults": num_results or self._max_results,
            "useAutoprompt": use_autoprompt,
        }
        if include_domains:
            payload["includeDomains"] = include_domains

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                resp = await client.post(
                    f"{self._base_url}/search",
                    json=payload,
                    headers=self._headers(),
                )
            except httpx.HTTPError as exc:
                raise ExaError(f"Exa search request failed: {exc}") from exc

        if resp.status_code >= 400:
            raise ExaError(
                f"Exa search returned HTTP {resp.status_code}: {resp.text[:300]}"
            )

        try:
            data = resp.json()
        except Exception as exc:
            raise ExaError(f"Exa search response not JSON: {resp.text[:300]}") from exc

        results_raw = data.get("results") or data.get("Result") or []
        results: list[ExaSearchResult] = []
        for r in results_raw:
            results.append(
                ExaSearchResult(
                    title=r.get("title", "") or "",
                    url=r.get("url", "") or "",
                    snippet=r.get("text", "") or r.get("snippet", "") or "",
                    published_date=r.get("publishedDate"),
                    author=r.get("author"),
                    score=r.get("score"),
                )
            )
        logger.info("Exa search query=%r returned %d results", query[:80], len(results))
        return results

    async def get_contents(
        self,
        urls: list[str],
        *,
        text: bool = True,
        summary: bool = False,
    ) -> list[ExaContent]:
        """Fetch the clean markdown/text content of one or more URLs via Exa.

        Useful as a fallback when direct HTTP fetch returns 403/anti-bot.

        Args:
            urls: List of URLs to fetch (max 10 per call to stay within the
                Exa rate limit).
            text: Include the full text (True) or just summary.
            summary: Include an AI-generated summary.
        """
        if not urls:
            return []
        if len(urls) > 10:
            urls = urls[:10]

        payload: dict[str, Any] = {
            "ids": urls,
            "text": text,
            "summary": summary,
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                resp = await client.post(
                    f"{self._base_url}/contents",
                    json=payload,
                    headers=self._headers(),
                )
            except httpx.HTTPError as exc:
                raise ExaError(f"Exa contents request failed: {exc}") from exc

        if resp.status_code >= 400:
            raise ExaError(
                f"Exa contents returned HTTP {resp.status_code}: {resp.text[:300]}"
            )

        try:
            data = resp.json()
        except Exception as exc:
            raise ExaError(f"Exa contents response not JSON: {resp.text[:300]}") from exc

        results_raw = data.get("results") or data.get("Result") or []
        contents: list[ExaContent] = []
        for r in results_raw:
            contents.append(
                ExaContent(
                    url=r.get("url", "") or "",
                    title=r.get("title"),
                    text=r.get("text", "") or "",
                    summary=r.get("summary"),
                )
            )
        logger.info("Exa contents fetched %d/%d URLs", len(contents), len(urls))
        return contents


def format_search_results_as_text(results: list[ExaSearchResult]) -> str:
    """Render Exa search results as a plain-text block for LLM context."""
    if not results:
        return ""
    lines = ["Web search results:"]
    for i, r in enumerate(results, 1):
        date = f" (published: {r.published_date})" if r.published_date else ""
        lines.append(
            f"\n[{i}] {r.title}\n"
            f"    URL: {r.url}{date}\n"
            f"    Excerpt: {r.snippet[:500]}"
        )
    return "\n".join(lines)


def format_contents_as_text(contents: list[ExaContent]) -> str:
    """Render Exa contents as a plain-text block for LLM context."""
    if not contents:
        return ""
    parts: list[str] = ["Fetched page contents:"]
    for c in contents:
        title_line = f"\n## {c.title or c.url}\n" if c.title else f"\n## {c.url}\n"
        body = c.text or c.summary or ""
        if c.summary:
            body = f"Summary: {c.summary}\n\n{body}"
        parts.append(f"{title_line}{body}\n")
    return "\n".join(parts)
