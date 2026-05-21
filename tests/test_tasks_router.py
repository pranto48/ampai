"""Tests for routers/tasks.py — Task CRUD endpoints.

Validates: Requirements 11.2, 11.4, 11.5, 11.6
"""

import sys
import os
import importlib.util
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

import pytest

# ── Mock heavy dependencies before importing the router ───────────────────────
# This avoids pulling in langchain, sqlalchemy engine creation, passlib, etc.

# Mock database module
_mock_database = MagicMock()
_mock_database.create_task = MagicMock(return_value=1)
_mock_database.list_tasks = MagicMock(return_value=([], 0))
_mock_database.update_task = MagicMock(return_value=True)
_mock_database.delete_task = MagicMock(return_value=True)
_mock_database.get_task_by_id = MagicMock(return_value=None)
_mock_database.get_all_sessions = MagicMock(return_value=[])
_mock_database.log_audit_event = MagicMock()
sys.modules.setdefault("database", _mock_database)

# Mock langchain and other heavy deps
sys.modules.setdefault("langchain_community", MagicMock())
sys.modules.setdefault("langchain_community.chat_message_histories", MagicMock())
sys.modules.setdefault("cryptography", MagicMock())
sys.modules.setdefault("cryptography.fernet", MagicMock())
sys.modules.setdefault("logging_utils", MagicMock())

# Mock jose for core.deps
_mock_jose = MagicMock()
_mock_jose.JWTError = Exception
sys.modules.setdefault("jose", _mock_jose)

# Mock core.helpers
_mock_helpers = MagicMock()
_mock_helpers._can_access_session = MagicMock(return_value=True)
_mock_helpers._load_config_list = MagicMock(return_value=[])
_mock_helpers._load_session_suggestions = MagicMock(return_value=[])
_mock_helpers._save_config_list = MagicMock()
_mock_helpers._save_session_suggestions = MagicMock()
sys.modules.setdefault("core.helpers", _mock_helpers)

# ── Import the router directly using importlib to bypass routers/__init__.py ──

_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _project_root)

# Import core.deps (lightweight, only needs jose which is mocked)
from core.deps import UserContext, require_authenticated_user

# Import core.models (lightweight pydantic models)
from core.models import TaskCreateRequest, TaskUpdateRequest, SuggestionTaskCreateRequest

# Load routers.tasks directly
_tasks_router_path = os.path.join(_project_root, "routers", "tasks.py")
_spec = importlib.util.spec_from_file_location("routers.tasks", _tasks_router_path)
_tasks_module = importlib.util.module_from_spec(_spec)
sys.modules["routers.tasks"] = _tasks_module
_spec.loader.exec_module(_tasks_module)

router = _tasks_module.router

# ── Set up test client ────────────────────────────────────────────────────────

from fastapi import FastAPI
from fastapi.testclient import TestClient

app = FastAPI()
app.include_router(router)


def _mock_user():
    return UserContext(username="testuser", role="user")


app.dependency_overrides[require_authenticated_user] = _mock_user
client = TestClient(app)


# ── GET /api/tasks ────────────────────────────────────────────────────────────


class TestListTasks:
    def test_default_pagination(self):
        """GET /api/tasks returns paginated results with default limit 20."""
        with patch.object(_tasks_module, "list_tasks", return_value=([], 0)) as mock_list:
            resp = client.get("/api/tasks")
            assert resp.status_code == 200
            data = resp.json()
            assert "tasks" in data
            assert data["limit"] == 20
            assert data["offset"] == 0
            assert data["total"] == 0
            assert data["has_more"] is False
            call_kwargs = mock_list.call_args[1]
            assert call_kwargs["username"] == "testuser"
            assert call_kwargs["limit"] == 20
            assert call_kwargs["offset"] == 0

    def test_with_filters(self):
        """GET /api/tasks supports status, priority, due date range, and search filters."""
        with patch.object(_tasks_module, "list_tasks", return_value=([{"id": 1, "title": "Test"}], 1)) as mock_list:
            resp = client.get(
                "/api/tasks",
                params={
                    "status": "todo",
                    "priority": "high",
                    "due_from": "2024-01-01",
                    "due_to": "2024-12-31",
                    "search": "meeting",
                    "limit": 10,
                    "offset": 5,
                },
            )
            assert resp.status_code == 200
            call_kwargs = mock_list.call_args[1]
            assert call_kwargs["status"] == "todo"
            assert call_kwargs["priority"] == "high"
            assert call_kwargs["due_from"] == "2024-01-01"
            assert call_kwargs["due_to"] == "2024-12-31"
            assert call_kwargs["search"] == "meeting"
            assert call_kwargs["limit"] == 10
            assert call_kwargs["offset"] == 5

    def test_invalid_status(self):
        """GET /api/tasks rejects invalid status values."""
        resp = client.get("/api/tasks", params={"status": "invalid"})
        assert resp.status_code == 400
        assert "Invalid status" in resp.json()["detail"]

    def test_invalid_priority(self):
        """GET /api/tasks rejects invalid priority values."""
        resp = client.get("/api/tasks", params={"priority": "invalid"})
        assert resp.status_code == 400
        assert "Invalid priority" in resp.json()["detail"]

    def test_has_more(self):
        """GET /api/tasks correctly reports has_more when more results exist."""
        tasks = [{"id": i, "title": f"Task {i}"} for i in range(5)]
        with patch.object(_tasks_module, "list_tasks", return_value=(tasks, 15)):
            resp = client.get("/api/tasks", params={"limit": 5})
            assert resp.status_code == 200
            data = resp.json()
            assert data["has_more"] is True
            assert data["total"] == 15

    def test_datetime_serialization(self):
        """GET /api/tasks serializes datetime objects to ISO strings."""
        now = datetime(2024, 6, 15, 10, 0, 0, tzinfo=timezone.utc)
        tasks = [{"id": 1, "title": "Test", "created_at": now, "updated_at": now, "due_at": now}]
        with patch.object(_tasks_module, "list_tasks", return_value=(tasks, 1)):
            resp = client.get("/api/tasks")
            assert resp.status_code == 200
            task = resp.json()["tasks"][0]
            assert task["created_at"] == "2024-06-15T10:00:00+00:00"
            assert task["updated_at"] == "2024-06-15T10:00:00+00:00"
            assert task["due_at"] == "2024-06-15T10:00:00+00:00"


# ── POST /api/tasks ───────────────────────────────────────────────────────────


class TestCreateTask:
    def test_success(self):
        """POST /api/tasks creates a task with valid data."""
        with patch.object(_tasks_module, "create_task", return_value=42) as mock_create, \
             patch.object(_tasks_module, "log_audit_event"):
            resp = client.post(
                "/api/tasks",
                json={
                    "title": "Buy groceries",
                    "description": "Milk, eggs, bread",
                    "priority": "medium",
                    "due_at": "2024-06-15T10:00:00Z",
                    "session_id": "sess-123",
                },
            )
            assert resp.status_code == 201
            data = resp.json()
            assert data["status"] == "success"
            assert data["id"] == 42
            mock_create.assert_called_once_with(
                title="Buy groceries",
                description="Milk, eggs, bread",
                priority="medium",
                due_at="2024-06-15T10:00:00Z",
                session_id="sess-123",
                username="testuser",
            )

    def test_title_too_long(self):
        """POST /api/tasks rejects title longer than 150 characters."""
        with patch.object(_tasks_module, "create_task") as mock_create:
            resp = client.post("/api/tasks", json={"title": "x" * 151})
            assert resp.status_code == 400
            assert "150 characters" in resp.json()["detail"]
            mock_create.assert_not_called()

    def test_description_too_long(self):
        """POST /api/tasks rejects description longer than 1000 characters."""
        with patch.object(_tasks_module, "create_task") as mock_create:
            resp = client.post(
                "/api/tasks", json={"title": "Valid title", "description": "x" * 1001}
            )
            assert resp.status_code == 400
            assert "1000 characters" in resp.json()["detail"]
            mock_create.assert_not_called()

    def test_empty_title(self):
        """POST /api/tasks rejects empty title."""
        with patch.object(_tasks_module, "create_task") as mock_create:
            resp = client.post("/api/tasks", json={"title": "   "})
            assert resp.status_code == 400
            assert "required" in resp.json()["detail"].lower()
            mock_create.assert_not_called()

    def test_invalid_priority(self):
        """POST /api/tasks rejects invalid priority."""
        with patch.object(_tasks_module, "create_task") as mock_create:
            resp = client.post("/api/tasks", json={"title": "Test", "priority": "critical"})
            assert resp.status_code == 400
            assert "Invalid priority" in resp.json()["detail"]
            mock_create.assert_not_called()

    def test_title_at_max_length(self):
        """POST /api/tasks accepts title at exactly 150 characters."""
        with patch.object(_tasks_module, "create_task", return_value=1), \
             patch.object(_tasks_module, "log_audit_event"):
            resp = client.post("/api/tasks", json={"title": "x" * 150})
            assert resp.status_code == 201

    def test_all_valid_priorities(self):
        """POST /api/tasks accepts all valid priority values."""
        for priority in ("low", "medium", "high", "urgent"):
            with patch.object(_tasks_module, "create_task", return_value=1), \
                 patch.object(_tasks_module, "log_audit_event"):
                resp = client.post("/api/tasks", json={"title": "Test", "priority": priority})
                assert resp.status_code == 201, f"Failed for priority={priority}"


# ── PATCH /api/tasks/{id} ─────────────────────────────────────────────────────


class TestUpdateTask:
    def test_status_transition_any_direction(self):
        """PATCH /api/tasks/{id} allows status transitions in any direction."""
        transitions = [
            ("todo", "in_progress"),
            ("in_progress", "done"),
            ("done", "todo"),
            ("todo", "done"),
            ("done", "in_progress"),
            ("in_progress", "todo"),
        ]
        for current, target in transitions:
            with patch.object(_tasks_module, "get_task_by_id", return_value={"id": 1, "status": current, "username": "testuser"}), \
                 patch.object(_tasks_module, "update_task", return_value=True), \
                 patch.object(_tasks_module, "log_audit_event"):
                resp = client.patch("/api/tasks/1", json={"status": target})
                assert resp.status_code == 200, f"Failed transition {current} -> {target}"

    def test_not_found(self):
        """PATCH /api/tasks/{id} returns 404 for non-existent task."""
        with patch.object(_tasks_module, "get_task_by_id", return_value=None):
            resp = client.patch("/api/tasks/999", json={"status": "done"})
            assert resp.status_code == 404

    def test_invalid_status(self):
        """PATCH /api/tasks/{id} rejects invalid status values."""
        with patch.object(_tasks_module, "get_task_by_id", return_value={"id": 1, "status": "todo", "username": "testuser"}):
            resp = client.patch("/api/tasks/1", json={"status": "cancelled"})
            assert resp.status_code == 400
            assert "Invalid status" in resp.json()["detail"]

    def test_title_too_long(self):
        """PATCH /api/tasks/{id} rejects title longer than 150 characters."""
        with patch.object(_tasks_module, "get_task_by_id", return_value={"id": 1, "status": "todo", "username": "testuser"}):
            resp = client.patch("/api/tasks/1", json={"title": "x" * 151})
            assert resp.status_code == 400
            assert "150 characters" in resp.json()["detail"]

    def test_description_too_long(self):
        """PATCH /api/tasks/{id} rejects description longer than 1000 characters."""
        with patch.object(_tasks_module, "get_task_by_id", return_value={"id": 1, "status": "todo", "username": "testuser"}):
            resp = client.patch("/api/tasks/1", json={"description": "x" * 1001})
            assert resp.status_code == 400
            assert "1000 characters" in resp.json()["detail"]

    def test_empty_update(self):
        """PATCH /api/tasks/{id} rejects request with no valid fields."""
        with patch.object(_tasks_module, "get_task_by_id", return_value={"id": 1, "status": "todo", "username": "testuser"}):
            resp = client.patch("/api/tasks/1", json={})
            assert resp.status_code == 400
            assert "No valid fields" in resp.json()["detail"]

    def test_invalid_priority(self):
        """PATCH /api/tasks/{id} rejects invalid priority values."""
        with patch.object(_tasks_module, "get_task_by_id", return_value={"id": 1, "status": "todo", "username": "testuser"}):
            resp = client.patch("/api/tasks/1", json={"priority": "critical"})
            assert resp.status_code == 400
            assert "Invalid priority" in resp.json()["detail"]


# ── DELETE /api/tasks/{id} ────────────────────────────────────────────────────


class TestDeleteTask:
    def test_success(self):
        """DELETE /api/tasks/{id} deletes an existing task."""
        with patch.object(_tasks_module, "get_task_by_id", return_value={"id": 1, "username": "testuser"}), \
             patch.object(_tasks_module, "delete_task", return_value=True) as mock_delete, \
             patch.object(_tasks_module, "log_audit_event"):
            resp = client.delete("/api/tasks/1")
            assert resp.status_code == 200
            assert resp.json()["status"] == "success"
            mock_delete.assert_called_once_with(1, username="testuser")

    def test_not_found(self):
        """DELETE /api/tasks/{id} returns 404 for non-existent task."""
        with patch.object(_tasks_module, "get_task_by_id", return_value=None):
            resp = client.delete("/api/tasks/999")
            assert resp.status_code == 404
