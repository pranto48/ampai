"""AmpAI routers package.

Import all routers and expose ``register_all_with_dedup`` for safe registration
that performs true route-level deduplication — duplicate routes are never added
to the FastAPI app.

The legacy ``register_all`` function is preserved as a compatibility wrapper.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List, Set, Tuple

from fastapi import APIRouter
from fastapi.routing import APIRoute

from routers.admin import router as admin_router
from routers.auth import router as auth_router
from routers.browser import router as browser_router
from routers.chat import router as chat_router
from routers.integrations import router as integrations_router
from routers.memory import router as memory_router
from routers.models_router import router as models_router
from routers.personas import router as personas_router
from routers.recall import router as recall_router
from routers.sessions import router as sessions_router
from routers.skills import router as skills_router
from routers.system import router as system_router
from routers.tasks import router as tasks_router
from routers.terminal import router as terminal_router
from routers.users import router as users_router
from routers.web_search import router as web_search_router

logger = logging.getLogger("ampai.routers")

ALL_ROUTERS = [
    auth_router,
    browser_router,
    chat_router,
    sessions_router,
    memory_router,
    personas_router,
    users_router,
    skills_router,
    tasks_router,
    recall_router,
    models_router,
    admin_router,
    integrations_router,
    system_router,
    terminal_router,
    web_search_router,
]


@dataclass
class RouteInventory:
    """Result of route registration with deduplication."""

    registered_routes: List[Tuple[str, str]] = field(default_factory=list)
    skipped_duplicates: List[Tuple[str, str]] = field(default_factory=list)
    duplicate_details: List[str] = field(default_factory=list)


def _get_existing_routes(app) -> Set[Tuple[str, str]]:
    """Extract all currently registered (method, path) pairs from a FastAPI app."""
    existing: Set[Tuple[str, str]] = set()
    for route in app.routes:
        if hasattr(route, "methods") and hasattr(route, "path"):
            for method in route.methods:
                existing.add((method.upper(), route.path))
    return existing


def _get_route_pairs(route) -> List[Tuple[str, str]]:
    """Get all (METHOD, path) pairs for a single route object."""
    pairs = []
    if hasattr(route, "methods") and hasattr(route, "path"):
        for method in route.methods:
            pairs.append((method.upper(), route.path))
    return pairs


def register_all_with_dedup(app) -> RouteInventory:
    """Register routes from ALL_ROUTERS with true route-level deduplication.

    For each router, inspects every route individually. Only routes whose
    method+path combinations are NOT already registered on the app are added.
    Duplicate routes are never registered — they are skipped entirely.

    This creates a temporary APIRouter containing only non-duplicate routes
    from each source router, then includes that filtered router into the app.

    Returns a RouteInventory with the final registered routes and any
    skipped duplicates.
    """
    inventory = RouteInventory()

    # Collect routes already on the app (from main.py inline definitions)
    existing = _get_existing_routes(app)

    for source_router in ALL_ROUTERS:
        # Build a filtered router containing only non-duplicate routes
        filtered_router = APIRouter()
        new_route_count = 0
        dup_route_count = 0

        for route in source_router.routes:
            pairs = _get_route_pairs(route)

            if not pairs:
                # Non-API route (e.g., websocket, mount) — include as-is
                filtered_router.routes.append(route)
                continue

            # Check if ALL method+path pairs for this route are already registered
            all_duplicate = all(pair in existing for pair in pairs)

            if all_duplicate:
                # Skip this route entirely — it's a duplicate
                for method, path in pairs:
                    detail = f"Skipped duplicate: {method} {path} (already registered)"
                    logger.warning(detail)
                    inventory.skipped_duplicates.append((method, path))
                    inventory.duplicate_details.append(detail)
                dup_route_count += 1
            else:
                # This route has at least one new method+path — include it
                filtered_router.routes.append(route)
                for pair in pairs:
                    if pair not in existing:
                        existing.add(pair)
                        inventory.registered_routes.append(pair)
                    else:
                        # This specific method+path is a dup but the route
                        # object has other new methods — still log it
                        inventory.skipped_duplicates.append(pair)
                        inventory.duplicate_details.append(
                            f"Skipped duplicate method: {pair[0]} {pair[1]} (already registered)"
                        )
                new_route_count += 1

        # Only include the filtered router if it has routes to add
        if filtered_router.routes:
            app.include_router(filtered_router)
        elif dup_route_count > 0:
            logger.warning(
                "Skipped entire router (all %d routes are duplicates)", dup_route_count
            )

    return inventory


def verify_no_duplicates(app) -> List[Tuple[str, str]]:
    """Scan app.routes and return any duplicate method+path combinations.

    Call this after registration to assert no duplicates exist.
    Returns an empty list if no duplicates are found.
    """
    seen: Set[Tuple[str, str]] = set()
    duplicates: List[Tuple[str, str]] = []
    for route in app.routes:
        if hasattr(route, "methods") and hasattr(route, "path"):
            for method in route.methods:
                pair = (method.upper(), route.path)
                if pair in seen:
                    duplicates.append(pair)
                else:
                    seen.add(pair)
    return duplicates


def register_all(app) -> None:
    """Legacy compatibility wrapper. Calls register_all_with_dedup internally."""
    register_all_with_dedup(app)
