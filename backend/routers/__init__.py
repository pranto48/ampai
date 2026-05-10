"""AmpAI routers package.

Import all routers and expose a ``register_all`` convenience function
that can be called from a lightweight bootstrap entry-point.
"""

from __future__ import annotations

from routers.admin import router as admin_router
from routers.auth import router as auth_router
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
from routers.users import router as users_router

ALL_ROUTERS = [
    auth_router,
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
]


def register_all(app) -> None:
    """Include every domain router into a FastAPI ``app`` instance."""
    for router in ALL_ROUTERS:
        app.include_router(router)
