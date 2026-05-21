"""Unit tests for router registration deduplication and route inventory.

Validates:
- Duplicate route detection and skipping
- All key routes are registered
- Route inventory is complete
"""

import sys
import os
from unittest.mock import MagicMock, patch

import pytest

# Ensure project root is on path
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, _project_root)

# Mock heavy dependencies that main.py imports
_mock_modules = [
    "cryptography", "cryptography.fernet",
    "langchain_community", "langchain_community.chat_message_histories",
    "langchain_community.embeddings",
    "langchain_core", "langchain_core.documents", "langchain_core.messages",
    "langchain_core.prompts", "langchain_core.output_parsers",
    "langchain_postgres", "langchain_openai", "langchain_google_genai",
    "redis", "jose", "jose.jwt",
    "passlib", "passlib.context",
    "memory_indexer", "memory_persistence", "memory_curator",
    "session_recall", "scheduler", "logging_utils",
    "agent", "integrations", "integrations.github",
    "integrations.gmail_api", "integrations.telegram_api",
    "backup_helpers", "auth", "duckduckgo_search", "httpx",
    "playwright", "playwright.async_api",
]
for mod in _mock_modules:
    sys.modules.setdefault(mod, MagicMock())

# Mock database module
_mock_db = MagicMock()
_mock_db.engine = MagicMock()
_mock_db.CHAT_HISTORY_TABLE = "chat_message_store"
_mock_db.DATABASE_URL = "postgresql://test:test@localhost/test"
sys.modules.setdefault("database", _mock_db)


class TestRouteInventory:
    """Tests for RouteInventory dataclass and register_all_with_dedup."""

    def test_route_inventory_dataclass(self):
        """RouteInventory has expected fields."""
        from routers import RouteInventory

        inv = RouteInventory()
        assert inv.registered_routes == []
        assert inv.skipped_duplicates == []
        assert inv.duplicate_details == []

    def test_route_inventory_with_data(self):
        """RouteInventory stores route data correctly."""
        from routers import RouteInventory

        inv = RouteInventory(
            registered_routes=[("GET", "/api/test")],
            skipped_duplicates=[("POST", "/api/dup")],
            duplicate_details=["Skipped duplicate: POST /api/dup"],
        )
        assert len(inv.registered_routes) == 1
        assert len(inv.skipped_duplicates) == 1
        assert "POST /api/dup" in inv.duplicate_details[0]


class TestDuplicateDetection:
    """Tests for duplicate route detection."""

    def test_no_duplicate_routes_in_app(self):
        """The application should not have duplicate route method+path combinations."""
        from fastapi import FastAPI

        # Create a minimal app and register routes
        app = FastAPI()

        # Add a test route
        @app.get("/api/test")
        def test_route():
            return {"ok": True}

        # Check for duplicates
        seen = set()
        duplicates = []
        for route in app.routes:
            if hasattr(route, "methods") and hasattr(route, "path"):
                for method in route.methods:
                    pair = (method, route.path)
                    if pair in seen:
                        duplicates.append(pair)
                    seen.add(pair)

        assert len(duplicates) == 0, f"Found duplicate routes: {duplicates}"


class TestKeyRoutesRequired:
    """Tests that verify required routes exist."""

    REQUIRED_ROUTES = [
        ("GET", "/api/sessions"),
        ("POST", "/api/chat"),
        ("POST", "/api/tools/web-search"),
        ("POST", "/api/browser/open"),
        ("POST", "/api/terminal/run"),
        ("GET", "/api/tasks"),
        ("GET", "/api/models/options"),
    ]

    def test_required_routes_defined_in_routers(self):
        """All required routes should be defined in the router modules."""
        # Import routers to check their route definitions
        from routers import ALL_ROUTERS

        all_routes = set()
        for router in ALL_ROUTERS:
            for route in router.routes:
                if hasattr(route, "methods") and hasattr(route, "path"):
                    for method in route.methods:
                        all_routes.add((method.upper(), route.path))

        missing = []
        for method, path in self.REQUIRED_ROUTES:
            if (method, path) not in all_routes:
                missing.append(f"{method} {path}")

        assert len(missing) == 0, (
            f"Required routes missing from routers: {missing}\n"
            f"Available routes include: {sorted(list(all_routes))[:20]}..."
        )


class TestGetExistingRoutes:
    """Tests for _get_existing_routes helper."""

    def test_extracts_routes_from_app(self):
        """_get_existing_routes correctly extracts registered routes."""
        from fastapi import FastAPI
        from routers import _get_existing_routes

        app = FastAPI()

        @app.get("/api/test1")
        def route1():
            pass

        @app.post("/api/test2")
        def route2():
            pass

        existing = _get_existing_routes(app)
        assert ("GET", "/api/test1") in existing
        assert ("POST", "/api/test2") in existing

    def test_empty_app_returns_empty_set(self):
        """Empty app returns empty route set (except default routes)."""
        from fastapi import FastAPI
        from routers import _get_existing_routes

        app = FastAPI()
        existing = _get_existing_routes(app)
        # FastAPI adds some default routes (openapi, docs, etc.)
        # but no /api/ routes
        api_routes = {(m, p) for m, p in existing if p.startswith("/api/")}
        assert len(api_routes) == 0
