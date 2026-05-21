"""Web Search router: POST /api/tools/web-search endpoint.

Accepts a query (1-500 chars), returns summarized search results within 15 seconds.
Logs each search to AuditLogger with query, provider, result_count, and latency_ms.
If all providers fail, returns a response with error status and no results.

Requirements: 7.1, 7.4, 7.6
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from core.audit import ACTION_WEB_SEARCH, AuditLogger
from core.deps import UserContext, require_authenticated_user
from database import engine as db_engine
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from services.web_search_service import WebSearchService

router = APIRouter(tags=["tools"])


# ── Request / Response models ─────────────────────────────────────────────────


class WebSearchRequest(BaseModel):
    """Request body for POST /api/tools/web-search."""

    query: str = Field(..., min_length=1, max_length=500)
    max_results: int = Field(default=5, ge=1, le=10)


class WebSearchHitResponse(BaseModel):
    """A single search result."""

    title: str
    url: str
    snippet: str
    provider: str
    timestamp: str


class WebSearchResponse(BaseModel):
    """Response for POST /api/tools/web-search."""

    query: str
    status: str
    provider: Optional[str] = None
    results: List[WebSearchHitResponse] = []
    result_count: int = 0
    summary: str = ""
    latency_ms: int = 0
    error: Optional[str] = None


# ── Service singletons ────────────────────────────────────────────────────────


def _get_web_search_service() -> WebSearchService:
    """Lazy-init WebSearchService with configured API keys."""
    configs: Dict[str, Any] = {
        "web_search_provider": os.getenv("WEB_SEARCH_PROVIDER", "duckduckgo"),
        "tavily_api_key": os.getenv("TAVILY_API_KEY", ""),
        "serpapi_api_key": os.getenv("SERPAPI_API_KEY", ""),
        "brave_api_key": os.getenv("BRAVE_API_KEY", ""),
    }
    return WebSearchService(configs=configs)


def _get_audit_logger() -> AuditLogger:
    """Lazy-init AuditLogger singleton."""
    return AuditLogger(engine=db_engine)


# ── POST /api/tools/web-search ────────────────────────────────────────────────


@router.post("/api/tools/web-search", response_model=WebSearchResponse)
def web_search(
    request: WebSearchRequest,
    current_user: UserContext = Depends(require_authenticated_user),
) -> WebSearchResponse:
    """
    Execute a web search query and return summarized results.

    - Accepts query (1-500 chars)
    - Returns summarized results within 15 seconds
    - Logs search to AuditLogger: query, provider, result_count, latency_ms
    - If all providers fail, returns response with error status
    """
    service = _get_web_search_service()
    audit = _get_audit_logger()

    # Execute search
    search_result = service.search(query=request.query, max_results=request.max_results)

    # Build response based on search outcome
    if search_result.status == "ok" and search_result.hits:
        results = [
            WebSearchHitResponse(
                title=hit.title,
                url=hit.url,
                snippet=hit.snippet,
                provider=hit.provider,
                timestamp=hit.timestamp,
            )
            for hit in search_result.hits
        ]
        summary = service.summarize_for_context(search_result.hits)

        response = WebSearchResponse(
            query=search_result.query,
            status="ok",
            provider=search_result.provider,
            results=results,
            result_count=len(results),
            summary=summary,
            latency_ms=search_result.latency_ms,
        )
    else:
        # All providers failed — return response without results with error status
        response = WebSearchResponse(
            query=search_result.query,
            status="error",
            provider=search_result.provider,
            results=[],
            result_count=0,
            summary="",
            latency_ms=search_result.latency_ms,
            error=search_result.error or "All search providers failed",
        )

    # Log to AuditLogger (Requirement 7.4)
    audit.log(
        username=current_user.username,
        action_type=ACTION_WEB_SEARCH,
        details={
            "query": request.query,
            "provider": response.provider,
            "result_count": response.result_count,
            "latency_ms": response.latency_ms,
        },
        category="web_search",
    )

    return response
