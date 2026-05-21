"""Unit tests for router registration deduplication and route inventory.

Validates:
- Router with all duplicate routes is skipped entirely
- Router with mixed duplicate and new routes registers only new routes
- app.routes has zero duplicate method+path pairs after registration
- Required routes still exist
- verify_no_duplicates works correctly
"""

import sys
import os
from unittest.mock import MagicMock, patch

import pytest

# Ensure project root is on path
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, _project_root)

# Mock heavy dependencies that router imports may pull in
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

from fastapi import APIRouter, FastAPI
from routers import (
    ALL_ROUTERS,
    RouteInventory,
    _get_existing_routes,
    register_all_with_dedup,
    verify_no_duplicates,
)


# ---------------------------------------------------------------------------
# Test: Router with all duplicate routes is skipped
# ---------------------------------------------------------------------------


class TestAllDuplicateRouterSkipped:
    """A router whose routes are all already registered is skipped entirely."""

    def test_all_duplicate_router_skipped(self):
        """If app already has GET /test, a router with only GET /test adds nothing."""
        app = FastAPI()

        # Pre-register a route on the app
        @app.get("/test")
        def existing():
            return {"ok": True}

        # Create a router with the same route
        dup_router = APIRouter()

        @dup_router.get("/test")
        def duplicate():
            return {"dup": True}

        # Temporarily replace ALL_ROUTERS
        import routers
        original = routers.ALL_ROUTERS
        routers.ALL_ROUTERS = [dup_router]

        try:
            inventory = register_all_with_dedup(app)
        finally:
            routers.ALL_ROUTERS = original

        # The duplicate should be skipped
        assert ("GET", "/test") in inventory.skipped_duplicates
        assert ("GET", "/test") not in inventory.registered_routes

        # Verify no duplicates in app
        duplicates = verify_no_duplicates(app)
        assert len(duplicates) == 0


# ---------------------------------------------------------------------------
# Test: Mixed duplicate and new routes — only new routes registered
# ---------------------------------------------------------------------------


class TestMixedRouterRegistersOnlyNew:
    """A router with both duplicate and new routes registers only the new ones."""

    def test_mixed_router_registers_only_new(self):
        """Router with GET /existing (dup) and GET /new registers only GET /new."""
        app = FastAPI()

        # Pre-register a route
        @app.get("/existing")
        def existing():
            return {"existing": True}

        # Create a router with one duplicate and one new route
        mixed_router = APIRouter()

        @mixed_router.get("/existing")
        def dup_route():
            return {"dup": True}

        @mixed_router.get("/new-route")
        def new_route():
            return {"new": True}

        import routers
        original = routers.ALL_ROUTERS
        routers.ALL_ROUTERS = [mixed_router]

        try:
            inventory = register_all_with_dedup(app)
        finally:
            routers.ALL_ROUTERS = original

        # /existing should be skipped, /new-route should be registered
        assert ("GET", "/existing") in inventory.skipped_duplicates
        assert ("GET", "/new-route") in inventory.registered_routes

        # Verify no duplicates in app
        duplicates = verify_no_duplicates(app)
        assert len(duplicates) == 0

    def test_new_route_is_callable(self):
        """The newly registered route should actually be reachable via app.routes."""
        app = FastAPI()

        @app.get("/existing")
        def existing():
            return {"existing": True}

        mixed_router = APIRouter()

        @mixed_router.get("/existing")
        def dup_route():
            return {"dup": True}

        @mixed_router.get("/new-endpoint")
        def new_endpoint():
            return {"new": True}

        import routers
        original = routers.ALL_ROUTERS
        routers.ALL_ROUTERS = [mixed_router]

        try:
            register_all_with_dedup(app)
        finally:
            routers.ALL_ROUTERS = original

        # Verify the new route is in app.routes
        registered = _get_existing_routes(app)
        assert ("GET", "/new-endpoint") in registered
        # Verify the existing route is still there
        assert ("GET", "/existing") in registered
        # Verify no duplicates
        assert verify_no_duplicates(app) == []


# ---------------------------------------------------------------------------
# Test: Zero duplicate method+path pairs after registration
# ---------------------------------------------------------------------------


class TestZeroDuplicatesAfterRegistration:
    """After registration, app.routes has zero duplicate method+path pairs."""

    def test_no_duplicates_after_dedup_registration(self):
        """register_all_with_dedup produces zero duplicates in app.routes."""
        app = FastAPI()

        # Pre-register some routes that will conflict with routers
        @app.get("/api/conflict1")
        def conflict1():
            pass

        @app.post("/api/conflict2")
        def conflict2():
            pass

        # Create routers with overlapping routes
        router_a = APIRouter()

        @router_a.get("/api/conflict1")
        def dup1():
            pass

        @router_a.get("/api/unique-a")
        def unique_a():
            pass

        router_b = APIRouter()

        @router_b.post("/api/conflict2")
        def dup2():
            pass

        @router_b.get("/api/unique-b")
        def unique_b():
            pass

        import routers
        original = routers.ALL_ROUTERS
        routers.ALL_ROUTERS = [router_a, router_b]

        try:
            register_all_with_dedup(app)
        finally:
            routers.ALL_ROUTERS = original

        # Final verification
        duplicates = verify_no_duplicates(app)
        assert duplicates == [], f"Found duplicates: {duplicates}"


# ---------------------------------------------------------------------------
# Test: verify_no_duplicates function
# ---------------------------------------------------------------------------


class TestVerifyNoDuplicates:
    """Tests for the verify_no_duplicates utility function."""

    def test_clean_app_returns_empty(self):
        """App with no duplicates returns empty list."""
        app = FastAPI()

        @app.get("/a")
        def a():
            pass

        @app.post("/b")
        def b():
            pass

        assert verify_no_duplicates(app) == []

    def test_detects_duplicates(self):
        """App with manually added duplicates is detected."""
        app = FastAPI()

        @app.get("/dup")
        def first():
            pass

        # Manually add a duplicate route (bypassing normal registration)
        from fastapi.routing import APIRoute

        dup_route = APIRoute(path="/dup", endpoint=lambda: None, methods=["GET"])
        app.routes.append(dup_route)

        duplicates = verify_no_duplicates(app)
        assert ("GET", "/dup") in duplicates


# ---------------------------------------------------------------------------
# Test: Required routes exist in ALL_ROUTERS
# ---------------------------------------------------------------------------


class TestRequiredRoutesExist:
    """All required routes are defined in the router modules."""

    REQUIRED_ROUTES = [
        ("GET", "/api/sessions"),
        ("POST", "/api/chat"),
        ("POST", "/api/tools/web-search"),
        ("POST", "/api/browser/open"),
        ("POST", "/api/terminal/run"),
        ("GET", "/api/tasks"),
        ("GET", "/api/models/options"),
    ]

    def test_required_routes_in_all_routers(self):
        """All required routes should be defined in ALL_ROUTERS."""
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
            f"Required routes missing from ALL_ROUTERS: {missing}"
        )

    def test_required_routes_registered_after_dedup(self):
        """Required routes are accessible after register_all_with_dedup."""
        app = FastAPI()

        import routers
        original = routers.ALL_ROUTERS
        # Use the real ALL_ROUTERS
        try:
            register_all_with_dedup(app)
        finally:
            routers.ALL_ROUTERS = original

        registered = _get_existing_routes(app)

        missing = []
        for method, path in self.REQUIRED_ROUTES:
            if (method, path) not in registered:
                missing.append(f"{method} {path}")

        assert len(missing) == 0, (
            f"Required routes not registered after dedup: {missing}"
        )


# ---------------------------------------------------------------------------
# Test: RouteInventory dataclass
# ---------------------------------------------------------------------------


class TestRouteInventory:
    """Tests for RouteInventory dataclass."""

    def test_empty_inventory(self):
        inv = RouteInventory()
        assert inv.registered_routes == []
        assert inv.skipped_duplicates == []
        assert inv.duplicate_details == []

    def test_inventory_with_data(self):
        inv = RouteInventory(
            registered_routes=[("GET", "/api/new")],
            skipped_duplicates=[("POST", "/api/dup")],
            duplicate_details=["Skipped duplicate: POST /api/dup (already registered)"],
        )
        assert len(inv.registered_routes) == 1
        assert len(inv.skipped_duplicates) == 1


# ---------------------------------------------------------------------------
# Test: _get_existing_routes helper
# ---------------------------------------------------------------------------


class TestGetExistingRoutes:
    """Tests for _get_existing_routes helper."""

    def test_extracts_routes_from_app(self):
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

    def test_empty_app_has_no_api_routes(self):
        app = FastAPI()
        existing = _get_existing_routes(app)
        api_routes = {(m, p) for m, p in existing if p.startswith("/api/")}
        assert len(api_routes) == 0
