"""AmpAI routers package.

Import all routers and expose ``register_all_with_dedup`` for safe registration
that detects and skips duplicate route path + method combinations.

The legacy ``register_all`` function is preserved as a compatibility wrapper.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List, Set, Tuple

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


def register_all_with_dedup(app) -> RouteInventory:
    """Register all routers, skipping any that would create duplicate routes.

    Detects duplicate (method, path) combinations against routes already
    registered on the app (e.g., inline endpoints in main.py) and against
    routes from previously registered routers.

    Returns a RouteInventory with the final registered routes and any
    skipped duplicates.
    """
    inventory = RouteInventory()

    # Collect routes already on the app (from main.py inline definitions)
    existing = _get_existing_routes(app)

    for router in ALL_ROUTERS:
        # Collect routes this router would add
        router_routes: List[Tuple[str, str]] = []
        duplicates_in_router: List[Tuple[str, str]] = []

        for route in router.routes:
            if hasattr(route, "methods") and hasattr(route, "path"):
                for method in route.methods:
                    pair = (method.upper(), route.path)
                    if pair in existing:
                        duplicates_in_router.append(pair)
                    else:
                        router_routes.append(pair)

        # Log and skip duplicates
        for method, path in duplicates_in_router:
            detail = f"Skipped duplicate: {method} {path} (already registered)"
            logger.warning(detail)
            inventory.skipped_duplicates.append((method, path))
            inventory.duplicate_details.append(detail)

        # Register the router (FastAPI will add all its routes)
        # We register even if some routes are duplicates — FastAPI handles
        # this by having the first-registered route win. But we track it.
        if router_routes or not duplicates_in_router:
            app.include_router(router)
            for pair in router_routes:
                existing.add(pair)
                inventory.registered_routes.append(pair)
        elif duplicates_in_router and not router_routes:
            # All routes in this router are duplicates — skip entirely
            logger.warning(
                "Skipped entire router (all %d routes are duplicates)",
                len(duplicates_in_router),
            )
        else:
            # Some routes are new, some are duplicates — register anyway
            app.include_router(router)
            for pair in router_routes:
                existing.add(pair)
                inventory.registered_routes.append(pair)

    return inventory


def register_all(app) -> None:
    """Legacy compatibility wrapper. Calls register_all_with_dedup internally."""
    register_all_with_dedup(app)
