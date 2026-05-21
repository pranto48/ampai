"""
Tests for the new memory router endpoints (Task 6.2).

Tests the endpoint handler logic by calling functions directly with
mocked dependencies. These tests validate:
- GET /api/memory/core: list core memories
- POST /api/memory/core: add explicit memory
- DELETE /api/memory/core/{id}: delete/forget memory
- GET /api/memory/inbox/pending: list pending candidates
- PATCH /api/memory/inbox/{id}/review: approve/reject candidate
- POST /api/memory/search: hybrid memory search
- AuditLogger integration for memory_write, memory_read, memory_delete events
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest

# ── Mock heavy dependencies before importing the router ───────────────────────

sys.modules.setdefault("cryptography", MagicMock())
sys.modules.setdefault("cryptography.fernet", MagicMock())
sys.modules.setdefault("langchain_community", MagicMock())
sys.modules.setdefault("langchain_community.chat_message_histories", MagicMock())
sys.modules.setdefault("langchain_community.embeddings", MagicMock())
sys.modules.setdefault("langchain_core", MagicMock())
sys.modules.setdefault("langchain_core.documents", MagicMock())
sys.modules.setdefault("langchain_core.messages", MagicMock())
sys.modules.setdefault("langchain_postgres", MagicMock())
sys.modules.setdefault("langchain_openai", MagicMock())
sys.modules.setdefault("langchain_google_genai", MagicMock())
sys.modules.setdefault("redis", MagicMock())
sys.modules.setdefault("passlib", MagicMock())
sys.modules.setdefault("passlib.context", MagicMock())
sys.modules.setdefault("session_recall", MagicMock())
sys.modules.setdefault("ampai_identity", MagicMock())
sys.modules.setdefault("logging_utils", MagicMock())

# Mock jose module properly for core.deps
mock_jose = MagicMock()
mock_jose.JWTError = Exception
mock_jose_jwt = MagicMock()
mock_jose_jwt.decode = MagicMock(return_value={"sub": "testuser", "role": "user"})
mock_jose_jwt.encode = MagicMock(return_value="fake-token")
mock_jose.jwt = mock_jose_jwt
sys.modules["jose"] = mock_jose
sys.modules["jose.jwt"] = mock_jose_jwt

# Mock database module

# Mock database module
mock_engine = MagicMock()
mock_engine.__bool__ = lambda self: True
mock_database = MagicMock()
mock_database.engine = mock_engine
mock_database.DATABASE_URL = "postgresql://test:test@localhost/test"
mock_database.get_config = MagicMock(return_value=None)
mock_database.add_core_memory = MagicMock(return_value=True)
mock_database.list_chat_messages = MagicMock(return_value=[])
mock_database.get_core_memories = MagicMock(return_value=[])
mock_database.delete_core_memory = MagicMock(return_value=True)
mock_database.update_core_memory = MagicMock(return_value=True)
mock_database.log_audit_event = MagicMock()
mock_database.get_all_sessions = MagicMock(return_value=[])
mock_database.get_all_configs = MagicMock(return_value={})
mock_database.session_exists = MagicMock(return_value=True)
mock_database.ensure_session_owner = MagicMock(return_value=True)
mock_database.get_session_owner = MagicMock(return_value="testuser")
mock_database.get_accessible_session_ids = MagicMock(return_value=[])
mock_database.list_shared_sessions_for_user = MagicMock(return_value=[])
mock_database.get_memory_analytics = MagicMock(return_value={})
mock_database.get_session_insight = MagicMock(return_value=None)
mock_database.list_curator_nudges = MagicMock(return_value=[])
mock_database.acknowledge_curator_nudge = MagicMock(return_value=True)
mock_database.memory_group_exists = MagicMock(return_value=True)
mock_database.memory_group_membership_exists = MagicMock(return_value=False)
mock_database.memory_group_session_share_exists = MagicMock(return_value=False)
mock_database.add_user_to_memory_group = MagicMock(return_value=True)
mock_database.remove_user_from_memory_group = MagicMock(return_value=True)
mock_database.create_memory_group = MagicMock(return_value=1)
mock_database.list_memory_groups_for_user = MagicMock(return_value=[])
mock_database.get_memory_group_members = MagicMock(return_value=[])
mock_database.get_memory_group_sessions = MagicMock(return_value=[])
mock_database.share_session_to_group = MagicMock(return_value=True)
mock_database.unshare_session_from_group = MagicMock(return_value=True)
mock_database.update_memory_candidate_status = MagicMock(return_value=True)
mock_database.enqueue_pending_reply_notification = MagicMock(return_value=True)
mock_database.get_effective_notification_preferences = MagicMock(return_value={})
sys.modules["database"] = mock_database

# Mock memory_persistence
mock_persistence_module = MagicMock()
mock_persistence_instance = MagicMock()
mock_persistence_instance._analyze_text_importance = MagicMock(return_value=0.5)
mock_persistence_module.memory_persistence_manager = mock_persistence_instance
sys.modules["memory_persistence"] = mock_persistence_module

# Mock memory_indexer
mock_indexer_module = MagicMock()
sys.modules["memory_indexer"] = mock_indexer_module

# Mock memory_curator
mock_curator_module = MagicMock()
mock_curator_module.create_nudge = MagicMock()
mock_curator_module.list_pending_nudges = MagicMock(return_value=[])
sys.modules["memory_curator"] = mock_curator_module

# Now import the modules under test
from core.deps import UserContext
from services.memory_service import MemorySearchResult, MemoryRetrievalMetadata

# Prevent routers/__init__.py from importing all other routers
# by pre-registering the routers package as already loaded
import types
import os
if "routers" not in sys.modules:
    routers_pkg = types.ModuleType("routers")
    routers_pkg.__path__ = [os.path.join(os.path.dirname(os.path.dirname(__file__)), "routers")]
    routers_pkg.__package__ = "routers"
    routers_pkg.__file__ = os.path.join(os.path.dirname(os.path.dirname(__file__)), "routers", "__init__.py")
    sys.modules["routers"] = routers_pkg

# Now import just routers.memory
import importlib
memory_router = importlib.import_module("routers.memory")


# ── Test fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture
def mock_user():
    return UserContext(username="testuser", role="user")


@pytest.fixture
def mock_audit():
    audit = MagicMock()
    return audit


@pytest.fixture
def mock_memory_service():
    svc = MagicMock()
    return svc


# ── Tests for list_core_memories (GET /api/memory/core) ───────────────────────


class TestListCoreMemories:
    def test_returns_memories_list(self, mock_user, mock_audit):
        """list_core_memories returns a list of memories from the database."""
        mock_rows = [
            (1, "testuser", "I like Python", "general", datetime(2024, 1, 1, tzinfo=timezone.utc)),
            (2, "testuser", "My cat is named Luna", "personal", datetime(2024, 1, 2, tzinfo=timezone.utc)),
        ]

        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchall.return_value = mock_rows
        mock_engine_ctx = MagicMock()
        mock_engine_ctx.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine_ctx.__exit__ = MagicMock(return_value=False)

        with patch("routers.memory.db_engine") as mock_eng, \
             patch("routers.memory._get_audit_logger", return_value=mock_audit):
            mock_eng.connect.return_value = mock_engine_ctx

            result = memory_router.list_core_memories(current_user=mock_user)

        assert "memories" in result
        assert result["total"] == 2
        assert len(result["memories"]) == 2
        assert result["memories"][0]["fact"] == "I like Python"
        assert result["memories"][1]["fact"] == "My cat is named Luna"

    def test_audit_logged_on_read(self, mock_user, mock_audit):
        """list_core_memories logs a memory_read audit event."""
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchall.return_value = []
        mock_engine_ctx = MagicMock()
        mock_engine_ctx.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine_ctx.__exit__ = MagicMock(return_value=False)

        with patch("routers.memory.db_engine") as mock_eng, \
             patch("routers.memory._get_audit_logger", return_value=mock_audit):
            mock_eng.connect.return_value = mock_engine_ctx

            memory_router.list_core_memories(current_user=mock_user)

        mock_audit.log.assert_called_once()
        call_kwargs = mock_audit.log.call_args[1]
        assert call_kwargs["action_type"] == "memory_read"
        assert call_kwargs["username"] == "testuser"
        assert call_kwargs["details"]["operation"] == "list_core"

    def test_handles_db_error_gracefully(self, mock_user, mock_audit):
        """list_core_memories returns empty list on database error."""
        mock_engine_ctx = MagicMock()
        mock_engine_ctx.__enter__ = MagicMock(side_effect=Exception("DB error"))
        mock_engine_ctx.__exit__ = MagicMock(return_value=False)

        with patch("routers.memory.db_engine") as mock_eng, \
             patch("routers.memory._get_audit_logger", return_value=mock_audit):
            mock_eng.connect.return_value = mock_engine_ctx

            result = memory_router.list_core_memories(current_user=mock_user)

        assert result["memories"] == []
        assert result["total"] == 0


# ── Tests for add_explicit_memory (POST /api/memory/core) ─────────────────────


class TestAddExplicitMemory:
    def test_saves_memory_successfully(self, mock_user, mock_audit, mock_memory_service):
        """add_explicit_memory saves a new explicit memory via MemoryService."""
        mock_memory_service.save_explicit_memory.return_value = {
            "id": 42,
            "username": "testuser",
            "fact": "I prefer dark mode",
            "category": "preferences",
            "created_at": "2024-01-01 00:00:00",
        }

        request = memory_router.ExplicitMemoryRequest(
            text="I prefer dark mode", category="preferences"
        )

        with patch("routers.memory._get_memory_service", return_value=mock_memory_service), \
             patch("routers.memory._get_audit_logger", return_value=mock_audit):
            result = memory_router.add_explicit_memory(request=request, current_user=mock_user)

        assert result["status"] == "success"
        assert result["memory"]["id"] == 42
        mock_memory_service.save_explicit_memory.assert_called_once_with(
            username="testuser",
            session_id=None,
            text="I prefer dark mode",
            category="preferences",
        )

    def test_raises_500_on_failure(self, mock_user, mock_audit, mock_memory_service):
        """add_explicit_memory raises HTTPException 500 if save fails."""
        mock_memory_service.save_explicit_memory.return_value = None
        request = memory_router.ExplicitMemoryRequest(text="test memory")

        with patch("routers.memory._get_memory_service", return_value=mock_memory_service), \
             patch("routers.memory._get_audit_logger", return_value=mock_audit):
            from fastapi import HTTPException
            with pytest.raises(HTTPException) as exc_info:
                memory_router.add_explicit_memory(request=request, current_user=mock_user)

        assert exc_info.value.status_code == 500

    def test_audit_logged_on_write(self, mock_user, mock_audit, mock_memory_service):
        """add_explicit_memory logs a memory_write audit event."""
        mock_memory_service.save_explicit_memory.return_value = {"id": 1, "category": "general"}
        request = memory_router.ExplicitMemoryRequest(text="test fact")

        with patch("routers.memory._get_memory_service", return_value=mock_memory_service), \
             patch("routers.memory._get_audit_logger", return_value=mock_audit):
            memory_router.add_explicit_memory(request=request, current_user=mock_user)

        mock_audit.log.assert_called_once()
        call_kwargs = mock_audit.log.call_args[1]
        assert call_kwargs["action_type"] == "memory_write"
        assert call_kwargs["details"]["operation"] == "add_explicit"


# ── Tests for delete_memory (DELETE /api/memory/core/{id}) ────────────────────


class TestDeleteMemory:
    def test_deletes_existing_memory(self, mock_user, mock_audit, mock_memory_service):
        """delete_memory deletes an existing memory and returns success."""
        mock_memory_service.forget_memory.return_value = True

        with patch("routers.memory._get_memory_service", return_value=mock_memory_service), \
             patch("routers.memory._get_audit_logger", return_value=mock_audit):
            result = memory_router.delete_memory(memory_id=5, current_user=mock_user)

        assert result["status"] == "success"
        assert result["deleted_id"] == 5
        mock_memory_service.forget_memory.assert_called_once_with(
            username="testuser", memory_id=5
        )

    def test_raises_404_if_not_found(self, mock_user, mock_audit, mock_memory_service):
        """delete_memory raises HTTPException 404 if memory not found."""
        mock_memory_service.forget_memory.return_value = False

        with patch("routers.memory._get_memory_service", return_value=mock_memory_service), \
             patch("routers.memory._get_audit_logger", return_value=mock_audit):
            from fastapi import HTTPException
            with pytest.raises(HTTPException) as exc_info:
                memory_router.delete_memory(memory_id=999, current_user=mock_user)

        assert exc_info.value.status_code == 404
        assert "not found" in exc_info.value.detail.lower()

    def test_audit_logged_on_delete(self, mock_user, mock_audit, mock_memory_service):
        """delete_memory logs a memory_delete audit event."""
        mock_memory_service.forget_memory.return_value = True

        with patch("routers.memory._get_memory_service", return_value=mock_memory_service), \
             patch("routers.memory._get_audit_logger", return_value=mock_audit):
            memory_router.delete_memory(memory_id=5, current_user=mock_user)

        mock_audit.log.assert_called_once()
        call_kwargs = mock_audit.log.call_args[1]
        assert call_kwargs["action_type"] == "memory_delete"
        assert call_kwargs["details"]["memory_id"] == 5


# ── Tests for list_pending_candidates_v2 (GET /api/memory/inbox/pending) ──────


class TestListPendingCandidates:
    def test_returns_pending_candidates(self, mock_user, mock_audit):
        """list_pending_candidates_v2 returns pending candidates from DB."""
        mock_rows = [
            (1, "testuser", "sess1", "candidate text", "auto", 0.5, "pending", 0.45,
             datetime(2024, 1, 1, tzinfo=timezone.utc)),
        ]

        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchall.return_value = mock_rows
        mock_engine_ctx = MagicMock()
        mock_engine_ctx.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine_ctx.__exit__ = MagicMock(return_value=False)

        with patch("routers.memory.db_engine") as mock_eng, \
             patch("routers.memory._get_audit_logger", return_value=mock_audit):
            mock_eng.connect.return_value = mock_engine_ctx

            result = memory_router.list_pending_candidates_v2(current_user=mock_user)

        assert "candidates" in result
        assert result["total"] == 1
        assert result["candidates"][0]["status"] == "pending"
        assert result["candidates"][0]["candidate_text"] == "candidate text"

    def test_limits_to_50_candidates(self, mock_user, mock_audit):
        """list_pending_candidates_v2 queries with LIMIT 50."""
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchall.return_value = []
        mock_engine_ctx = MagicMock()
        mock_engine_ctx.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine_ctx.__exit__ = MagicMock(return_value=False)

        with patch("routers.memory.db_engine") as mock_eng, \
             patch("routers.memory._get_audit_logger", return_value=mock_audit):
            mock_eng.connect.return_value = mock_engine_ctx

            memory_router.list_pending_candidates_v2(current_user=mock_user)

        # Verify the SQL query contains LIMIT 50
        call_args = mock_conn.execute.call_args
        sql_text = str(call_args[0][0])
        assert "LIMIT 50" in sql_text

    def test_audit_logged_on_inbox_read(self, mock_user, mock_audit):
        """list_pending_candidates_v2 logs a memory_read audit event."""
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchall.return_value = []
        mock_engine_ctx = MagicMock()
        mock_engine_ctx.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine_ctx.__exit__ = MagicMock(return_value=False)

        with patch("routers.memory.db_engine") as mock_eng, \
             patch("routers.memory._get_audit_logger", return_value=mock_audit):
            mock_eng.connect.return_value = mock_engine_ctx

            memory_router.list_pending_candidates_v2(current_user=mock_user)

        mock_audit.log.assert_called_once()
        call_kwargs = mock_audit.log.call_args[1]
        assert call_kwargs["action_type"] == "memory_read"
        assert call_kwargs["details"]["operation"] == "list_inbox_pending"


# ── Tests for review_memory_candidate_v2 (PATCH /api/memory/inbox/{id}/review)


class TestReviewCandidate:
    def test_approve_candidate(self, mock_user, mock_audit, mock_memory_service):
        """review_memory_candidate_v2 approves a candidate via MemoryService."""
        mock_memory_service.approve_candidate.return_value = {
            "candidate_id": 10,
            "core_memory_id": 42,
            "username": "testuser",
            "fact": "approved fact",
            "status": "approved",
        }

        request = memory_router.InboxActionRequest(action="approve")

        with patch("routers.memory._get_memory_service", return_value=mock_memory_service), \
             patch("routers.memory._get_audit_logger", return_value=mock_audit):
            result = memory_router.review_memory_candidate_v2(
                candidate_id=10, request=request, current_user=mock_user
            )

        assert result["status"] == "approved"
        assert result["result"]["core_memory_id"] == 42

    def test_reject_candidate(self, mock_user, mock_audit, mock_memory_service):
        """review_memory_candidate_v2 rejects a candidate via MemoryService."""
        mock_memory_service.reject_candidate.return_value = {
            "id": 10,
            "username": "testuser",
            "candidate_text": "some text",
            "status": "rejected",
        }

        request = memory_router.InboxActionRequest(action="reject")

        with patch("routers.memory._get_memory_service", return_value=mock_memory_service), \
             patch("routers.memory._get_audit_logger", return_value=mock_audit):
            result = memory_router.review_memory_candidate_v2(
                candidate_id=10, request=request, current_user=mock_user
            )

        assert result["status"] == "rejected"

    def test_raises_404_if_approve_not_found(self, mock_user, mock_audit, mock_memory_service):
        """review_memory_candidate_v2 raises 404 if candidate not found on approve."""
        mock_memory_service.approve_candidate.return_value = None
        request = memory_router.InboxActionRequest(action="approve")

        with patch("routers.memory._get_memory_service", return_value=mock_memory_service), \
             patch("routers.memory._get_audit_logger", return_value=mock_audit):
            from fastapi import HTTPException
            with pytest.raises(HTTPException) as exc_info:
                memory_router.review_memory_candidate_v2(
                    candidate_id=999, request=request, current_user=mock_user
                )

        assert exc_info.value.status_code == 404

    def test_raises_404_if_reject_not_found(self, mock_user, mock_audit, mock_memory_service):
        """review_memory_candidate_v2 raises 404 if candidate not found on reject."""
        mock_memory_service.reject_candidate.return_value = None
        request = memory_router.InboxActionRequest(action="reject")

        with patch("routers.memory._get_memory_service", return_value=mock_memory_service), \
             patch("routers.memory._get_audit_logger", return_value=mock_audit):
            from fastapi import HTTPException
            with pytest.raises(HTTPException) as exc_info:
                memory_router.review_memory_candidate_v2(
                    candidate_id=999, request=request, current_user=mock_user
                )

        assert exc_info.value.status_code == 404

    def test_raises_400_for_invalid_action(self, mock_user, mock_audit, mock_memory_service):
        """review_memory_candidate_v2 raises 400 for invalid action."""
        request = memory_router.InboxActionRequest(action="invalid")

        with patch("routers.memory._get_memory_service", return_value=mock_memory_service), \
             patch("routers.memory._get_audit_logger", return_value=mock_audit):
            from fastapi import HTTPException
            with pytest.raises(HTTPException) as exc_info:
                memory_router.review_memory_candidate_v2(
                    candidate_id=10, request=request, current_user=mock_user
                )

        assert exc_info.value.status_code == 400

    def test_audit_logged_on_approve(self, mock_user, mock_audit, mock_memory_service):
        """review_memory_candidate_v2 logs memory_write on approve."""
        mock_memory_service.approve_candidate.return_value = {
            "candidate_id": 10, "core_memory_id": 42
        }
        request = memory_router.InboxActionRequest(action="approve")

        with patch("routers.memory._get_memory_service", return_value=mock_memory_service), \
             patch("routers.memory._get_audit_logger", return_value=mock_audit):
            memory_router.review_memory_candidate_v2(
                candidate_id=10, request=request, current_user=mock_user
            )

        mock_audit.log.assert_called_once()
        call_kwargs = mock_audit.log.call_args[1]
        assert call_kwargs["action_type"] == "memory_write"

    def test_audit_logged_on_reject(self, mock_user, mock_audit, mock_memory_service):
        """review_memory_candidate_v2 logs memory_delete on reject."""
        mock_memory_service.reject_candidate.return_value = {"id": 10, "status": "rejected"}
        request = memory_router.InboxActionRequest(action="reject")

        with patch("routers.memory._get_memory_service", return_value=mock_memory_service), \
             patch("routers.memory._get_audit_logger", return_value=mock_audit):
            memory_router.review_memory_candidate_v2(
                candidate_id=10, request=request, current_user=mock_user
            )

        mock_audit.log.assert_called_once()
        call_kwargs = mock_audit.log.call_args[1]
        assert call_kwargs["action_type"] == "memory_delete"


# ── Tests for search_memory (POST /api/memory/search) ─────────────────────────


class TestSearchMemory:
    def test_search_returns_results_with_metadata(self, mock_user, mock_audit, mock_memory_service):
        """search_memory returns search results with retrieval metadata."""
        mock_memory_service.search_memory.return_value = MemorySearchResult(
            memories=[{"fact": "I like Python"}],
            metadata=MemoryRetrievalMetadata(
                retrieved_count=1,
                context_chars=14,
                pipeline="hybrid",
                latency_ms=25,
            ),
        )

        request = memory_router.MemorySearchRequest(query="python")

        with patch("routers.memory._get_memory_service", return_value=mock_memory_service), \
             patch("routers.memory._get_audit_logger", return_value=mock_audit):
            result = memory_router.search_memory(request=request, current_user=mock_user)

        assert "memories" in result
        assert "metadata" in result
        assert result["metadata"]["retrieved_count"] == 1
        assert result["metadata"]["pipeline"] == "hybrid"
        assert result["metadata"]["latency_ms"] == 25
        assert result["memories"][0]["fact"] == "I like Python"

    def test_search_passes_all_params_to_service(self, mock_user, mock_audit, mock_memory_service):
        """search_memory passes all configurable settings to MemoryService."""
        mock_memory_service.search_memory.return_value = MemorySearchResult(
            memories=[],
            metadata=MemoryRetrievalMetadata(
                retrieved_count=0, context_chars=0, pipeline="hybrid", latency_ms=5
            ),
        )

        request = memory_router.MemorySearchRequest(
            query="test query",
            limit=3,
            mode="vector_only",
            category="work",
            date_from="2024-01-01",
            date_to="2024-12-31",
            recency_bias=0.5,
            char_budget=800,
        )

        with patch("routers.memory._get_memory_service", return_value=mock_memory_service), \
             patch("routers.memory._get_audit_logger", return_value=mock_audit):
            memory_router.search_memory(request=request, current_user=mock_user)

        mock_memory_service.search_memory.assert_called_once_with(
            username="testuser",
            query="test query",
            limit=3,
            mode="vector_only",
            category="work",
            date_from="2024-01-01",
            date_to="2024-12-31",
            recency_bias=0.5,
            char_budget=800,
        )

    def test_search_audit_logged(self, mock_user, mock_audit, mock_memory_service):
        """search_memory logs a memory_read audit event."""
        mock_memory_service.search_memory.return_value = MemorySearchResult(
            memories=[],
            metadata=MemoryRetrievalMetadata(
                retrieved_count=0, context_chars=0, pipeline="hybrid", latency_ms=5
            ),
        )

        request = memory_router.MemorySearchRequest(query="test")

        with patch("routers.memory._get_memory_service", return_value=mock_memory_service), \
             patch("routers.memory._get_audit_logger", return_value=mock_audit):
            memory_router.search_memory(request=request, current_user=mock_user)

        mock_audit.log.assert_called_once()
        call_kwargs = mock_audit.log.call_args[1]
        assert call_kwargs["action_type"] == "memory_read"
        assert call_kwargs["details"]["operation"] == "search"
        assert call_kwargs["details"]["query_length"] == 4
