"""
Web Search Service — multi-provider web search with fallback chain.

Supports DuckDuckGo (default, no key), Tavily, SerpAPI, and Brave Search.
Tries providers in order until one succeeds, with a 10-second timeout per provider.
Compresses results to a configurable char_budget (default 1200 chars).

Requirements: 7.1, 7.2, 7.3, 7.5, 7.6
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

DEFAULT_CHAR_BUDGET = 1200
PROVIDER_TIMEOUT_SECONDS = 10
MAX_RESULTS_DEFAULT = 5


@dataclass
class SearchHit:
    """A single web search result."""

    title: str
    url: str
    snippet: str
    provider: str
    timestamp: str


@dataclass
class WebSearchResult:
    """Result of a web search operation."""

    hits: List[SearchHit] = field(default_factory=list)
    provider: Optional[str] = None
    query: str = ""
    status: str = "ok"
    error: Optional[str] = None
    latency_ms: int = 0


# ---------------------------------------------------------------------------
# WebSearchService
# ---------------------------------------------------------------------------


class WebSearchService:
    """
    Multi-provider web search with ordered fallback.

    Provider priority: DuckDuckGo → Tavily → SerpAPI → Brave Search.
    Each provider gets a 10-second timeout before falling back to the next.
    """

    PROVIDERS = ["duckduckgo", "tavily", "serpapi", "brave"]

    def __init__(self, configs: Optional[Dict[str, Any]] = None):
        """
        Initialize with configuration dict.

        Expected config keys:
            - web_search_provider: preferred provider (optional)
            - tavily_api_key: API key for Tavily
            - serpapi_api_key: API key for SerpAPI
            - brave_api_key: API key for Brave Search
        """
        self.configs = configs or {}
        self.provider_order = self._resolve_provider_order()

    def _resolve_provider_order(self) -> List[str]:
        """
        Resolve provider order. DuckDuckGo is always first (no key needed).
        Other providers are included only if their API key is configured.
        """
        order = ["duckduckgo"]

        # Add providers that have API keys configured
        if self.configs.get("tavily_api_key"):
            order.append("tavily")
        if self.configs.get("serpapi_api_key"):
            order.append("serpapi")
        if self.configs.get("brave_api_key"):
            order.append("brave")

        return order

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def search(self, query: str, max_results: int = MAX_RESULTS_DEFAULT) -> WebSearchResult:
        """
        Try providers in order until one succeeds.

        Each provider has a 10-second timeout. On failure, falls back to next.
        Returns WebSearchResult with hits, provider used, and status.
        """
        if not query or not query.strip():
            return WebSearchResult(
                query=query or "",
                status="error",
                error="Empty query",
            )

        query = query.strip()
        max_results = max(1, min(max_results, 10))
        start_time = time.time()
        errors: List[str] = []

        for provider in self.provider_order:
            try:
                hits = self._search_provider(provider, query, max_results)
                if hits:
                    latency_ms = int((time.time() - start_time) * 1000)
                    return WebSearchResult(
                        hits=hits,
                        provider=provider,
                        query=query,
                        status="ok",
                        latency_ms=latency_ms,
                    )
                else:
                    errors.append(f"{provider}: no results")
            except Exception as exc:
                error_msg = f"{provider}: {str(exc)[:200]}"
                errors.append(error_msg)
                logger.warning("Web search provider %s failed: %s", provider, exc)

        # All providers failed
        latency_ms = int((time.time() - start_time) * 1000)
        return WebSearchResult(
            query=query,
            status="failed",
            error="; ".join(errors),
            latency_ms=latency_ms,
        )

    def summarize_for_context(
        self, results: List[SearchHit], char_budget: int = DEFAULT_CHAR_BUDGET
    ) -> str:
        """
        Compress search results into a context string within char_budget.

        Each result is formatted as "Title: snippet (url)" and truncated
        to fit within the budget.
        """
        if not results:
            return ""

        char_budget = max(200, min(char_budget, 4000))
        lines: List[str] = []
        remaining = char_budget

        for hit in results:
            if remaining <= 0:
                break

            # Format: "Title: snippet (url)"
            line = f"{hit.title}: {hit.snippet}"
            if hit.url:
                line += f" ({hit.url})"

            # Truncate if exceeds remaining budget
            if len(line) > remaining:
                truncate_at = max(0, remaining - 3)
                line = line[:truncate_at].rstrip() + "..."

            lines.append(line)
            remaining -= len(line) + 1  # +1 for newline separator

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Provider implementations
    # ------------------------------------------------------------------

    def _search_provider(
        self, provider: str, query: str, max_results: int
    ) -> List[SearchHit]:
        """Dispatch to the appropriate provider search method."""
        dispatch = {
            "duckduckgo": self._search_duckduckgo,
            "tavily": self._search_tavily,
            "serpapi": self._search_serpapi,
            "brave": self._search_brave,
        }
        handler = dispatch.get(provider)
        if not handler:
            raise ValueError(f"Unknown provider: {provider}")
        return handler(query, max_results)

    def _search_duckduckgo(self, query: str, max_results: int) -> List[SearchHit]:
        """Search using DuckDuckGo (no API key required)."""
        from duckduckgo_search import DDGS

        timestamp = datetime.now(timezone.utc).isoformat()
        hits: List[SearchHit] = []

        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))

        for r in results:
            hits.append(
                SearchHit(
                    title=r.get("title", ""),
                    url=r.get("href", r.get("link", "")),
                    snippet=r.get("body", r.get("snippet", "")),
                    provider="duckduckgo",
                    timestamp=timestamp,
                )
            )

        return hits

    def _search_tavily(self, query: str, max_results: int) -> List[SearchHit]:
        """Search using Tavily API."""
        api_key = self.configs.get("tavily_api_key")
        if not api_key:
            raise ValueError("Tavily API key not configured")

        timestamp = datetime.now(timezone.utc).isoformat()

        with httpx.Client(timeout=PROVIDER_TIMEOUT_SECONDS) as client:
            response = client.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": api_key,
                    "query": query,
                    "max_results": max_results,
                    "include_answer": False,
                },
            )
            response.raise_for_status()
            data = response.json()

        hits: List[SearchHit] = []
        for r in data.get("results", []):
            hits.append(
                SearchHit(
                    title=r.get("title", ""),
                    url=r.get("url", ""),
                    snippet=r.get("content", "")[:500],
                    provider="tavily",
                    timestamp=timestamp,
                )
            )

        return hits

    def _search_serpapi(self, query: str, max_results: int) -> List[SearchHit]:
        """Search using SerpAPI."""
        api_key = self.configs.get("serpapi_api_key")
        if not api_key:
            raise ValueError("SerpAPI key not configured")

        timestamp = datetime.now(timezone.utc).isoformat()

        with httpx.Client(timeout=PROVIDER_TIMEOUT_SECONDS) as client:
            response = client.get(
                "https://serpapi.com/search",
                params={
                    "api_key": api_key,
                    "q": query,
                    "num": max_results,
                    "engine": "google",
                },
            )
            response.raise_for_status()
            data = response.json()

        hits: List[SearchHit] = []
        for r in data.get("organic_results", []):
            hits.append(
                SearchHit(
                    title=r.get("title", ""),
                    url=r.get("link", ""),
                    snippet=r.get("snippet", ""),
                    provider="serpapi",
                    timestamp=timestamp,
                )
            )

        return hits[:max_results]

    def _search_brave(self, query: str, max_results: int) -> List[SearchHit]:
        """Search using Brave Search API."""
        api_key = self.configs.get("brave_api_key")
        if not api_key:
            raise ValueError("Brave Search API key not configured")

        timestamp = datetime.now(timezone.utc).isoformat()

        with httpx.Client(timeout=PROVIDER_TIMEOUT_SECONDS) as client:
            response = client.get(
                "https://api.search.brave.com/res/v1/web/search",
                params={
                    "q": query,
                    "count": max_results,
                },
                headers={
                    "Accept": "application/json",
                    "Accept-Encoding": "gzip",
                    "X-Subscription-Token": api_key,
                },
            )
            response.raise_for_status()
            data = response.json()

        hits: List[SearchHit] = []
        for r in data.get("web", {}).get("results", []):
            hits.append(
                SearchHit(
                    title=r.get("title", ""),
                    url=r.get("url", ""),
                    snippet=r.get("description", ""),
                    provider="brave",
                    timestamp=timestamp,
                )
            )

        return hits[:max_results]
