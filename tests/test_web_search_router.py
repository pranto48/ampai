"""Tests for routers/web_search.py — POST /api/tools/web-search endpoint.

Validates:
- Accept query (1-500 chars), return summarized results
- Log search to AuditLogger: query, provider, result_count, latency_ms
- If all providers fail, return response without search results with error status
- Query validation (empty, too long)

Requirements: 7.1, 7.4, 7.6
"""

import sys
from unittest.mock import MagicMock, patch

# Mock heavy dependencies before importing the module under test
_mock_modules = [
    "cryptography", "cryptography.fernet",
    "langchain_community", "langchain_community.chat_message_histories",
    "langchain_community.embeddings",
    "langchain_core", "langchain_core.prompts", "langchain_core.messages",
    "langchain_core.output_parsers",
    "redis",
    "jose", "jose.jwt",
    "passlib", "passlib.context",
    "memory_indexer", "memory_persistence", "memory_curator",
    "session_recall",
    "scheduler",
    "logging_utils",
    "agent",
    "integrations", "integrations.github", "integrations.gmail_api",
    "integrations.telegram_api",
    "backup_helpers",
    "auth",
    "duckduckgo_search",
]
for mod in _mock_modules:
    sys.modules.setdefault(mod, MagicMock())

# Mock database module with needed attributes
_mock_db = MagicMock()
_mock_db.CHAT_HISTORY_TABLE = "chat_message_store"
_mock_db.engine = MagicMock()
sys.modules.setdefault("database", _mock_db)

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.deps import UserContext, require_authenticated_user
from services.web_search_service import SearchHit, WebSearchResult

import routers.web_search as web_search_module

router = web_search_module.router


# ---------------------------------------------------------------------------
# Test app setup
# ---------------------------------------------------------------------------


def _create_test_app():
    app = FastAPI()
    app.include_router(router)
    return app


def _mock_user(username="testuser", role="user"):
    return UserContext(username=username, role=role)


def _sample_hits():
    return [
        SearchHit(
            title="Python Docs",
            url="https://docs.python.org",
            snippet="Official Python documentation",
            provider="duckduckgo",
            timestamp="2024-01-01T00:00:00Z",
        ),
        SearchHit(
            title="FastAPI",
            url="https://fastapi.tiangolo.com",
            snippet="FastAPI framework documentation",
            provider="duckduckgo",
            timestamp="2024-01-01T00:00:00Z",
        ),
    ]


# ---------------------------------------------------------------------------
# POST /api/tools/web-search — success path
# ---------------------------------------------------------------------------


class TestWebSearchSuccess:
    """Tests for successful web search requests."""

    def setup_method(self):
        self.app = _create_test_app()
        self.app.dependency_overrides[require_authenticated_user] = lambda: _mock_user()
        self.client = TestClient(self.app)

    def teardown_method(self):
        self.app.dependency_overrides.clear()

    @patch("routers.web_search._get_audit_logger")
    @patch("routers.web_search._get_web_search_service")
    def test_search_returns_results(self, mock_service_factory, mock_audit_factory):
        hits = _sample_hits()
        mock_service = MagicMock()
        mock_service.search.return_value = WebSearchResult(
            hits=hits,
            provider="duckduckgo",
            query="python docs",
            status="ok",
            latency_ms=150,
        )
        mock_service.summarize_for_context.return_value = (
            "Python Docs: Official Python documentation (https://docs.python.org)"
        )
        mock_service_factory.return_value = mock_service

        mock_audit = MagicMock()
        mock_audit_factory.return_value = mock_audit

        resp = self.client.post(
            "/api/tools/web-search", json={"query": "python docs"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["query"] == "python docs"
        assert data["provider"] == "duckduckgo"
        assert data["result_count"] == 2
        assert len(data["results"]) == 2
        assert data["results"][0]["title"] == "Python Docs"
        assert data["latency_ms"] == 150
        assert data["summary"] != ""
        assert data["error"] is None

    @patch("routers.web_search._get_audit_logger")
    @patch("routers.web_search._get_web_search_service")
    def test_search_logs_to_audit(self, mock_service_factory, mock_audit_factory):
        """Requirement 7.4: search is logged to AuditLogger."""
        hits = _sample_hits()
        mock_service = MagicMock()
        mock_service.search.return_value = WebSearchResult(
            hits=hits,
            provider="duckduckgo",
            query="test query",
            status="ok",
            latency_ms=200,
        )
        mock_service.summarize_for_context.return_value = "summary"
        mock_service_factory.return_value = mock_service

        mock_audit = MagicMock()
        mock_audit_factory.return_value = mock_audit

        self.client.post("/api/tools/web-search", json={"query": "test query"})

        mock_audit.log.assert_called_once()
        call_kwargs = mock_audit.log.call_args[1]
        assert call_kwargs["username"] == "testuser"
        assert call_kwargs["action_type"] == "web_search"
        assert call_kwargs["details"]["query"] == "test query"
        assert call_kwargs["details"]["provider"] == "duckduckgo"
        assert call_kwargs["details"]["result_count"] == 2
        assert call_kwargs["details"]["latency_ms"] == 200

    @patch("routers.web_search._get_audit_logger")
    @patch("routers.web_search._get_web_search_service")
    def test_search_with_max_results(self, mock_service_factory, mock_audit_factory):
        mock_service = MagicMock()
        mock_service.search.return_value = WebSearchResult(
            hits=_sample_hits()[:1],
            provider="duckduckgo",
            query="test",
            status="ok",
            latency_ms=100,
        )
        mock_service.summarize_for_context.return_value = "summary"
        mock_service_factory.return_value = mock_service
        mock_audit_factory.return_value = MagicMock()

        resp = self.client.post(
            "/api/tools/web-search", json={"query": "test", "max_results": 1}
        )
        assert resp.status_code == 200
        mock_service.search.assert_called_once_with(query="test", max_results=1)


# ---------------------------------------------------------------------------
# POST /api/tools/web-search — all providers fail
# ---------------------------------------------------------------------------


class TestWebSearchAllFail:
    """Tests for when all search providers fail (Requirement 7.6)."""

    def setup_method(self):
        self.app = _create_test_app()
        self.app.dependency_overrides[require_authenticated_user] = lambda: _mock_user()
        self.client = TestClient(self.app)

    def teardown_method(self):
        self.app.dependency_overrides.clear()

    @patch("routers.web_search._get_audit_logger")
    @patch("routers.web_search._get_web_search_service")
    def test_all_providers_fail_returns_error_status(
        self, mock_service_factory, mock_audit_factory
    ):
        mock_service = MagicMock()
        mock_service.search.return_value = WebSearchResult(
            hits=[],
            provider=None,
            query="failing query",
            status="failed",
            error="duckduckgo: timeout; tavily: no key",
            latency_ms=10500,
        )
        mock_service_factory.return_value = mock_service
        mock_audit_factory.return_value = MagicMock()

        resp = self.client.post(
            "/api/tools/web-search", json={"query": "failing query"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "error"
        assert data["result_count"] == 0
        assert data["results"] == []
        assert data["error"] is not None
        assert "duckduckgo" in data["error"]

    @patch("routers.web_search._get_audit_logger")
    @patch("routers.web_search._get_web_search_service")
    def test_all_fail_still_logs_audit(self, mock_service_factory, mock_audit_factory):
        """Even on failure, the search attempt is logged."""
        mock_service = MagicMock()
        mock_service.search.return_value = WebSearchResult(
            hits=[],
            provider=None,
            query="fail query",
            status="failed",
            error="all failed",
            latency_ms=5000,
        )
        mock_service_factory.return_value = mock_service

        mock_audit = MagicMock()
        mock_audit_factory.return_value = mock_audit

        self.client.post("/api/tools/web-search", json={"query": "fail query"})

        mock_audit.log.assert_called_once()
        call_kwargs = mock_audit.log.call_args[1]
        assert call_kwargs["details"]["result_count"] == 0
        assert call_kwargs["details"]["latency_ms"] == 5000


# ---------------------------------------------------------------------------
# POST /api/tools/web-search — validation
# ---------------------------------------------------------------------------


class TestWebSearchValidation:
    """Tests for request validation (Requirement 7.1: 1-500 chars)."""

    def setup_method(self):
        self.app = _create_test_app()
        self.app.dependency_overrides[require_authenticated_user] = lambda: _mock_user()
        self.client = TestClient(self.app)

    def teardown_method(self):
        self.app.dependency_overrides.clear()

    def test_empty_query_returns_422(self):
        resp = self.client.post("/api/tools/web-search", json={"query": ""})
        assert resp.status_code == 422

    def test_query_too_long_returns_422(self):
        long_query = "x" * 501
        resp = self.client.post("/api/tools/web-search", json={"query": long_query})
        assert resp.status_code == 422

    def test_missing_query_returns_422(self):
        resp = self.client.post("/api/tools/web-search", json={})
        assert resp.status_code == 422

    @patch("routers.web_search._get_audit_logger")
    @patch("routers.web_search._get_web_search_service")
    def test_query_at_max_length_accepted(self, mock_service_factory, mock_audit_factory):
        mock_service = MagicMock()
        mock_service.search.return_value = WebSearchResult(
            hits=[], provider=None, query="x" * 500, status="failed",
            error="no results", latency_ms=100,
        )
        mock_service_factory.return_value = mock_service
        mock_audit_factory.return_value = MagicMock()

        resp = self.client.post(
            "/api/tools/web-search", json={"query": "x" * 500}
        )
        assert resp.status_code == 200

    def test_max_results_below_1_returns_422(self):
        resp = self.client.post(
            "/api/tools/web-search", json={"query": "test", "max_results": 0}
        )
        assert resp.status_code == 422

    def test_max_results_above_10_returns_422(self):
        resp = self.client.post(
            "/api/tools/web-search", json={"query": "test", "max_results": 11}
        )
        assert resp.status_code == 422
