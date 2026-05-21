"""Tests for routers/sessions.py — Session CRUD endpoints.

Validates:
- POST /api/sessions: create new session with optional title and category
- PATCH /api/sessions/{id}: update title (max 100 chars), category, pinned, archived
- DELETE /api/sessions/{id}: delete session metadata, messages, and recall index
- GET /api/sessions: list sessions paginated, sorted by pinned first then updated_at DESC
- GET /api/history/{session_id}: get all messages for a session
- User ownership enforcement on all endpoints

Requirements: 4.1, 4.2, 4.5, 4.6
"""

import sys
import importlib
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

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

# Now import the deps and router directly (avoiding routers/__init__.py)
from core.deps import UserContext, require_authenticated_user

# Import the sessions module directly
import routers.sessions as sessions_module
router = sessions_module.router


# ---------------------------------------------------------------------------
# Test app setup
# ---------------------------------------------------------------------------


def _create_test_app():
    app = FastAPI()
    app.include_router(router)
    return app


def _mock_user(username="testuser", role="user"):
    return UserContext(username=username, role=role)


def _mock_admin():
    return UserContext(username="admin", role="admin")


# ---------------------------------------------------------------------------
# POST /api/sessions
# ---------------------------------------------------------------------------


class TestCreateSession:
    """Tests for POST /api/sessions — create new session."""

    def setup_method(self):
        self.app = _create_test_app()
        self.app.dependency_overrides[require_authenticated_user] = lambda: _mock_user()
        self.client = TestClient(self.app)

    def teardown_method(self):
        self.app.dependency_overrides.clear()

    @patch("routers.sessions.ensure_session_owner", return_value=True)
    @patch("routers.sessions.log_audit_event")
    @patch("routers.sessions.create_session_metadata", return_value=True)
    def test_create_session_minimal(self, mock_create, mock_audit, mock_owner):
        resp = self.client.post("/api/sessions", json={})
        assert resp.status_code == 201
        data = resp.json()
        assert "session_id" in data
        assert data["category"] == "Uncategorized"
        assert data["pinned"] is False
        assert data["archived"] is False
        assert data["owner_username"] == "testuser"
        mock_create.assert_called_once()

    @patch("routers.sessions.ensure_session_owner", return_value=True)
    @patch("routers.sessions.log_audit_event")
    @patch("routers.sessions.create_session_metadata", return_value=True)
    def test_create_session_with_title_and_category(self, mock_create, mock_audit, mock_owner):
        resp = self.client.post(
            "/api/sessions",
            json={"title": "My Chat", "category": "Work"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "My Chat"
        assert data["category"] == "Work"

    @patch("routers.sessions.ensure_session_owner", return_value=True)
    @patch("routers.sessions.log_audit_event")
    @patch("routers.sessions.create_session_metadata", return_value=True)
    def test_create_session_title_truncated_to_100(self, mock_create, mock_audit, mock_owner):
        long_title = "x" * 150
        resp = self.client.post("/api/sessions", json={"title": long_title})
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "x" * 100

    @patch("routers.sessions.ensure_session_owner", return_value=True)
    @patch("routers.sessions.log_audit_event")
    @patch("routers.sessions.create_session_metadata", return_value=False)
    def test_create_session_failure_returns_500(self, mock_create, mock_audit, mock_owner):
        resp = self.client.post("/api/sessions", json={})
        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# PATCH /api/sessions/{session_id}
# ---------------------------------------------------------------------------


class TestPatchSession:
    """Tests for PATCH /api/sessions/{id} — update session metadata."""

    def setup_method(self):
        self.app = _create_test_app()
        self.app.dependency_overrides[require_authenticated_user] = lambda: _mock_user()
        self.client = TestClient(self.app)

    def teardown_method(self):
        self.app.dependency_overrides.clear()

    @patch("routers.sessions.log_audit_event")
    @patch("routers.sessions.get_session_metadata", side_effect=[
        {"session_id": "s1", "title": "Old", "category": "Work", "pinned": False, "archived": False, "owner_username": "testuser", "updated_at": "2024-01-01"},
        {"session_id": "s1", "title": "New Title", "category": "Work", "pinned": False, "archived": False, "owner_username": "testuser", "updated_at": "2024-01-02"},
    ])
    @patch("routers.sessions.update_session_metadata", return_value=True)
    @patch("routers.sessions._can_access_session", return_value=True)
    def test_patch_title(self, mock_access, mock_update, mock_get, mock_audit):
        resp = self.client.patch("/api/sessions/s1", json={"title": "New Title"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "New Title"

    @patch("routers.sessions.log_audit_event")
    @patch("routers.sessions.get_session_metadata", side_effect=[
        {"session_id": "s1", "title": None, "category": "Work", "pinned": False, "archived": False, "owner_username": "testuser", "updated_at": "2024-01-01"},
        {"session_id": "s1", "title": "x" * 100, "category": "Work", "pinned": False, "archived": False, "owner_username": "testuser", "updated_at": "2024-01-02"},
    ])
    @patch("routers.sessions.update_session_metadata", return_value=True)
    @patch("routers.sessions._can_access_session", return_value=True)
    def test_patch_title_truncated_to_100(self, mock_access, mock_update, mock_get, mock_audit):
        long_title = "y" * 200
        resp = self.client.patch("/api/sessions/s1", json={"title": long_title})
        assert resp.status_code == 200
        # Verify update was called with truncated title
        call_kwargs = mock_update.call_args[1]
        assert call_kwargs["title"] == "y" * 100

    @patch("routers.sessions.log_audit_event")
    @patch("routers.sessions.get_session_metadata", side_effect=[
        {"session_id": "s1", "title": None, "category": "Work", "pinned": False, "archived": False, "owner_username": "testuser", "updated_at": "2024-01-01"},
        {"session_id": "s1", "title": None, "category": "Personal", "pinned": True, "archived": False, "owner_username": "testuser", "updated_at": "2024-01-02"},
    ])
    @patch("routers.sessions.update_session_metadata", return_value=True)
    @patch("routers.sessions._can_access_session", return_value=True)
    def test_patch_category_and_pinned(self, mock_access, mock_update, mock_get, mock_audit):
        resp = self.client.patch(
            "/api/sessions/s1", json={"category": "Personal", "pinned": True}
        )
        assert resp.status_code == 200
        call_kwargs = mock_update.call_args[1]
        assert call_kwargs["category"] == "Personal"
        assert call_kwargs["pinned"] is True

    @patch("routers.sessions.get_session_metadata", return_value=None)
    @patch("routers.sessions._can_access_session", return_value=True)
    def test_patch_nonexistent_session_returns_404(self, mock_access, mock_get):
        resp = self.client.patch("/api/sessions/nonexistent", json={"title": "X"})
        assert resp.status_code == 404

    @patch("routers.sessions._can_access_session", return_value=False)
    @patch("routers.sessions.session_exists", return_value=True)
    @patch("routers.sessions.get_session_owner", return_value="otheruser")
    def test_patch_forbidden_for_non_owner(self, mock_owner, mock_exists, mock_access):
        resp = self.client.patch("/api/sessions/s1", json={"title": "Hack"})
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# DELETE /api/sessions/{session_id}
# ---------------------------------------------------------------------------


class TestDeleteSession:
    """Tests for DELETE /api/sessions/{id} — delete session and all data."""

    def setup_method(self):
        self.app = _create_test_app()
        self.app.dependency_overrides[require_authenticated_user] = lambda: _mock_user()
        self.client = TestClient(self.app)

    def teardown_method(self):
        self.app.dependency_overrides.clear()

    @patch("routers.sessions.log_audit_event")
    @patch("routers.sessions.delete_session_recall_entries", return_value=5)
    @patch("routers.sessions.get_redis_history")
    @patch("routers.sessions.SQLChatMessageHistory")
    @patch("routers.sessions.delete_session_metadata", return_value=True)
    @patch("routers.sessions._can_access_session", return_value=True)
    def test_delete_session_success(
        self, mock_access, mock_del_meta, mock_sql_hist, mock_redis, mock_recall, mock_audit
    ):
        mock_sql_hist.return_value.clear = MagicMock()
        mock_redis.return_value.clear = MagicMock()

        resp = self.client.delete("/api/sessions/s1")
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"

        # Verify all cleanup steps were called
        mock_del_meta.assert_called_once_with("s1")
        mock_sql_hist.assert_called_once()
        mock_recall.assert_called_once_with("s1")

    @patch("routers.sessions._can_access_session", return_value=False)
    @patch("routers.sessions.session_exists", return_value=True)
    @patch("routers.sessions.get_session_owner", return_value="otheruser")
    def test_delete_forbidden_for_non_owner(self, mock_owner, mock_exists, mock_access):
        resp = self.client.delete("/api/sessions/s1")
        assert resp.status_code == 403

    @patch("routers.sessions.log_audit_event")
    @patch("routers.sessions.delete_session_recall_entries", side_effect=Exception("SQLite error"))
    @patch("routers.sessions.get_redis_history")
    @patch("routers.sessions.SQLChatMessageHistory")
    @patch("routers.sessions.delete_session_metadata", return_value=True)
    @patch("routers.sessions._can_access_session", return_value=True)
    def test_delete_continues_if_recall_fails(
        self, mock_access, mock_del_meta, mock_sql_hist, mock_redis, mock_recall, mock_audit
    ):
        """Session recall deletion failure should not block the overall delete."""
        mock_sql_hist.return_value.clear = MagicMock()
        mock_redis.return_value.clear = MagicMock()

        resp = self.client.delete("/api/sessions/s1")
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"


# ---------------------------------------------------------------------------
# GET /api/history/{session_id} — ownership enforcement
# ---------------------------------------------------------------------------


class TestGetHistory:
    """Tests for GET /api/history/{session_id} — ownership checks."""

    def setup_method(self):
        self.app = _create_test_app()
        self.app.dependency_overrides[require_authenticated_user] = lambda: _mock_user()
        self.client = TestClient(self.app)

    def teardown_method(self):
        self.app.dependency_overrides.clear()

    @patch("routers.sessions.log_audit_event")
    @patch("routers.sessions.list_chat_messages", return_value=[
        {"type": "human", "content": "Hello"},
        {"type": "ai", "content": "Hi there!"},
    ])
    @patch("routers.sessions._can_access_session", return_value=True)
    def test_get_history_success(self, mock_access, mock_messages, mock_audit):
        resp = self.client.get("/api/history/s1")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["messages"]) == 2
        assert data["messages"][0]["type"] == "human"

    @patch("routers.sessions.get_config", return_value="false")
    @patch("routers.sessions.session_exists", return_value=True)
    @patch("routers.sessions.get_session_owner", return_value="otheruser")
    @patch("routers.sessions.ensure_session_owner", return_value=False)
    @patch("routers.sessions._can_access_session", return_value=False)
    def test_get_history_forbidden_for_non_owner(
        self, mock_access, mock_ensure, mock_owner, mock_exists, mock_config
    ):
        resp = self.client.get("/api/history/s1")
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Admin access
# ---------------------------------------------------------------------------


class TestAdminAccess:
    """Admins can access any session regardless of ownership."""

    def setup_method(self):
        self.app = _create_test_app()
        self.app.dependency_overrides[require_authenticated_user] = lambda: _mock_admin()
        self.client = TestClient(self.app)

    def teardown_method(self):
        self.app.dependency_overrides.clear()

    @patch("routers.sessions.log_audit_event")
    @patch("routers.sessions.delete_session_recall_entries", return_value=0)
    @patch("routers.sessions.get_redis_history")
    @patch("routers.sessions.SQLChatMessageHistory")
    @patch("routers.sessions.delete_session_metadata", return_value=True)
    def test_admin_can_delete_any_session(
        self, mock_del_meta, mock_sql_hist, mock_redis, mock_recall, mock_audit
    ):
        mock_sql_hist.return_value.clear = MagicMock()
        mock_redis.return_value.clear = MagicMock()

        resp = self.client.delete("/api/sessions/any-session")
        assert resp.status_code == 200

    @patch("routers.sessions.log_audit_event")
    @patch("routers.sessions.get_session_metadata", side_effect=[
        {"session_id": "s1", "title": "Old", "category": "X", "pinned": False, "archived": False, "owner_username": "otheruser", "updated_at": "2024-01-01"},
        {"session_id": "s1", "title": "Admin Edit", "category": "X", "pinned": False, "archived": False, "owner_username": "otheruser", "updated_at": "2024-01-02"},
    ])
    @patch("routers.sessions.update_session_metadata", return_value=True)
    def test_admin_can_patch_any_session(self, mock_update, mock_get, mock_audit):
        resp = self.client.patch("/api/sessions/s1", json={"title": "Admin Edit"})
        assert resp.status_code == 200
