"""Tests for chat message metadata persistence (Task 7.2).

Validates that:
- ChatRequest accepts the extended payload fields (enable_browser_tools, enable_terminal_tools)
- persist_chat_message_metadata stores full turn metadata in chat_message_store
- Metadata includes user message, assistant response, timestamp, model provider,
  memory retrieval metadata, web search metadata, and tool/action metadata
"""

import sys
import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch, call
from contextlib import contextmanager

import pytest

# Mock heavy dependencies before importing modules under test
sys.modules.setdefault("cryptography", MagicMock())
sys.modules.setdefault("cryptography.fernet", MagicMock())
sys.modules.setdefault("langchain_community", MagicMock())
sys.modules.setdefault("langchain_community.chat_message_histories", MagicMock())
sys.modules.setdefault("langchain_community.embeddings", MagicMock())
sys.modules.setdefault("langchain_core", MagicMock())
sys.modules.setdefault("langchain_core.documents", MagicMock())
sys.modules.setdefault("langchain_postgres", MagicMock())
sys.modules.setdefault("langchain_openai", MagicMock())
sys.modules.setdefault("langchain_google_genai", MagicMock())
sys.modules.setdefault("logging_utils", MagicMock())

from core.models import ChatRequest, Attachment


# ---------------------------------------------------------------------------
# ChatRequest extended payload
# ---------------------------------------------------------------------------


class TestChatRequestExtendedPayload:
    """Verify ChatRequest accepts all fields from the extended payload."""

    def test_accepts_enable_browser_tools(self):
        req = ChatRequest(
            session_id="sess-1",
            message="hello",
            enable_browser_tools=True,
        )
        assert req.enable_browser_tools is True

    def test_enable_browser_tools_defaults_false(self):
        req = ChatRequest(session_id="sess-1", message="hello")
        assert req.enable_browser_tools is False

    def test_accepts_enable_terminal_tools(self):
        req = ChatRequest(
            session_id="sess-1",
            message="hello",
            enable_terminal_tools=True,
        )
        assert req.enable_terminal_tools is True

    def test_enable_terminal_tools_defaults_false(self):
        req = ChatRequest(session_id="sess-1", message="hello")
        assert req.enable_terminal_tools is False

    def test_full_extended_payload(self):
        """Verify all fields from the design spec are accepted."""
        req = ChatRequest(
            session_id="sess-abc",
            message="What's the weather?",
            model_type="openrouter",
            model_name="mistral-7b",
            memory_mode="indexed",
            memory_top_k=3,
            memory_recency_bias=0.5,
            memory_category_filter="personal",
            use_web_search=True,
            enable_browser_tools=True,
            enable_terminal_tools=False,
            chat_output_mode="compact",
            attachments=[
                Attachment(filename="doc.pdf", url="/uploads/doc.pdf", type="application/pdf")
            ],
        )
        assert req.session_id == "sess-abc"
        assert req.message == "What's the weather?"
        assert req.model_type == "openrouter"
        assert req.model_name == "mistral-7b"
        assert req.memory_mode == "indexed"
        assert req.memory_top_k == 3
        assert req.memory_recency_bias == 0.5
        assert req.memory_category_filter == "personal"
        assert req.use_web_search is True
        assert req.enable_browser_tools is True
        assert req.enable_terminal_tools is False
        assert req.chat_output_mode == "compact"
        assert len(req.attachments) == 1


# ---------------------------------------------------------------------------
# persist_chat_message_metadata
# ---------------------------------------------------------------------------


class TestPersistChatMessageMetadata:
    """Tests for the persist_chat_message_metadata function.

    Since the database module may be mocked by other test files when running
    the full suite, we test the function logic by importing it fresh or
    testing the core behavior directly.
    """

    @pytest.fixture
    def mock_db_engine(self):
        """Create a mock SQLAlchemy engine."""
        engine = MagicMock()
        conn = MagicMock()
        result = MagicMock()
        result.first.return_value = (42,)
        conn.execute.return_value = result

        @contextmanager
        def connect_ctx():
            yield conn

        engine.connect = connect_ctx
        return engine, conn

    @pytest.fixture(autouse=True)
    def _ensure_real_database_module(self):
        """Ensure we have the real database module for these tests."""
        # If database module was replaced by a mock (e.g., by test_memory_service),
        # we need to detect it and skip gracefully.
        import database as db_mod
        # A real module has __file__; a MagicMock does not
        if not hasattr(db_mod, "__file__") or db_mod.__file__ is None:
            pytest.skip("database module is mocked by another test; skipping DB tests")

    def test_persists_metadata_record(self, mock_db_engine):
        engine, conn = mock_db_engine

        import database
        with patch.object(database, "engine", engine):
            record_id = database.persist_chat_message_metadata(
                session_id="sess-1",
                username="alice",
                user_message="Hello AI",
                assistant_response="Hi Alice!",
                model_provider="ollama",
                model_name="llama3",
                memory_retrieval_metadata={"retrieved_count": 3, "context_chars": 800},
                web_search_metadata={"enabled": True, "provider": "duckduckgo"},
                tool_action_metadata={"enable_browser_tools": False},
            )

        assert record_id == 42
        conn.execute.assert_called_once()
        call_args = conn.execute.call_args[0][1]
        assert call_args["session_id"] == "sess-1"

        # Verify the stored JSON contains all expected fields
        stored_json = json.loads(call_args["message"])
        assert stored_json["type"] == "turn_metadata"
        assert stored_json["username"] == "alice"
        assert stored_json["user_message"] == "Hello AI"
        assert stored_json["assistant_response"] == "Hi Alice!"
        assert stored_json["model_provider"] == "ollama"
        assert stored_json["model_name"] == "llama3"
        assert stored_json["memory_retrieval"]["retrieved_count"] == 3
        assert stored_json["web_search"]["provider"] == "duckduckgo"
        assert stored_json["tool_action"]["enable_browser_tools"] is False
        assert "timestamp" in stored_json

    def test_returns_none_when_engine_is_none(self):
        import database
        with patch.object(database, "engine", None):
            result = database.persist_chat_message_metadata(
                session_id="sess-1",
                username="alice",
                user_message="test",
                assistant_response="response",
                model_provider="ollama",
            )
        assert result is None

    def test_returns_none_on_db_error(self, mock_db_engine):
        engine, conn = mock_db_engine
        conn.execute.side_effect = Exception("DB error")

        import database
        with patch.object(database, "engine", engine):
            result = database.persist_chat_message_metadata(
                session_id="sess-1",
                username="alice",
                user_message="test",
                assistant_response="response",
                model_provider="ollama",
            )
        assert result is None

    def test_caps_user_message_length(self, mock_db_engine):
        engine, conn = mock_db_engine

        import database
        with patch.object(database, "engine", engine):
            long_message = "x" * 20000
            database.persist_chat_message_metadata(
                session_id="sess-1",
                username="alice",
                user_message=long_message,
                assistant_response="ok",
                model_provider="ollama",
            )

        call_args = conn.execute.call_args[0][1]
        stored_json = json.loads(call_args["message"])
        assert len(stored_json["user_message"]) <= 10000

    def test_defaults_empty_metadata_dicts(self, mock_db_engine):
        engine, conn = mock_db_engine

        import database
        with patch.object(database, "engine", engine):
            database.persist_chat_message_metadata(
                session_id="sess-1",
                username="alice",
                user_message="hi",
                assistant_response="hello",
                model_provider="ollama",
            )

        call_args = conn.execute.call_args[0][1]
        stored_json = json.loads(call_args["message"])
        assert stored_json["memory_retrieval"] == {}
        assert stored_json["web_search"] == {}
        assert stored_json["tool_action"] == {}
