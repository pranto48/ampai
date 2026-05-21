"""
Unit tests for services/memory_service.py

Tests the MemoryService facade using mocked database engine and indexer
to validate core logic without requiring a live database.
"""

import sys
import time
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

# Mock heavy dependencies before importing the module under test
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

# Mock database and memory modules to avoid DB connection at import time
mock_engine = MagicMock()
mock_engine.__bool__ = lambda self: True

sys.modules.setdefault("logging_utils", MagicMock())

# Patch database module
import importlib
mock_database = MagicMock()
mock_database.engine = mock_engine
mock_database.DATABASE_URL = "postgresql://test:test@localhost/test"
mock_database.get_config = MagicMock(return_value=None)
mock_database.add_core_memory = MagicMock(return_value=True)
mock_database.list_chat_messages = MagicMock(return_value=[])
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

# Mock ampai_identity
sys.modules.setdefault("ampai_identity", MagicMock())

from services.memory_service import (
    DEFAULT_CHAR_BUDGET,
    IMPORTANCE_THRESHOLD,
    MAX_EXPLICIT_MEMORY_CHARS,
    MemoryRetrievalMetadata,
    MemorySearchResult,
    MemoryService,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


class FakeRow:
    """Simulates a SQLAlchemy result row with index access."""

    def __init__(self, *values):
        self._values = values

    def __getitem__(self, idx):
        return self._values[idx]


class FakeResult:
    """Simulates a SQLAlchemy execute result."""

    def __init__(self, rows=None):
        self._rows = rows or []

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return self._rows


class FakeConnection:
    """Simulates a SQLAlchemy connection context manager."""

    def __init__(self, results=None):
        self.executed = []
        self._results = results or []
        self._result_idx = 0

    def execute(self, stmt, params=None):
        self.executed.append((stmt, params))
        if self._result_idx < len(self._results):
            result = self._results[self._result_idx]
            self._result_idx += 1
            return result
        return FakeResult()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class FakeEngine:
    """Simulates a SQLAlchemy engine with begin() context manager."""

    def __init__(self, connection=None):
        self.connection = connection or FakeConnection()

    def begin(self):
        return self.connection

    def connect(self):
        return self.connection


@pytest.fixture
def mock_indexer():
    indexer = MagicMock()
    indexer.enabled = True
    indexer.search_facts.return_value = ["fact one", "fact two", "fact three"]
    indexer.last_retrieval_stats = {
        "pipeline": "hybrid",
        "latency_ms": 42,
    }
    indexer.add_fact = MagicMock()
    return indexer


@pytest.fixture
def mock_persistence():
    with patch("services.memory_service.memory_persistence_manager") as mock_pm:
        mock_pm._analyze_text_importance.return_value = 0.5
        yield mock_pm


# ---------------------------------------------------------------------------
# Tests: save_chat_turn
# ---------------------------------------------------------------------------


class TestSaveChatTurn:
    def test_returns_none_for_empty_content(self, mock_indexer, mock_persistence):
        svc = MemoryService(db_engine=FakeEngine(), indexer=mock_indexer)
        assert svc.save_chat_turn("user1", "sess1", "human", "") is None
        assert svc.save_chat_turn("user1", "sess1", "human", "   ") is None

    def test_returns_none_when_importance_below_threshold(self, mock_indexer, mock_persistence):
        mock_persistence._analyze_text_importance.return_value = 0.10
        svc = MemoryService(db_engine=FakeEngine(), indexer=mock_indexer)
        result = svc.save_chat_turn("user1", "sess1", "human", "hi")
        assert result is None

    def test_creates_candidate_when_importance_above_threshold(self, mock_indexer, mock_persistence):
        mock_persistence._analyze_text_importance.return_value = 0.5
        fake_conn = FakeConnection(results=[
            FakeResult([FakeRow(42, "2024-01-01T00:00:00")])
        ])
        fake_engine = FakeEngine(connection=fake_conn)
        svc = MemoryService(db_engine=fake_engine, indexer=mock_indexer)

        result = svc.save_chat_turn("user1", "sess1", "human", "Remember my birthday is Jan 1")
        assert result is not None
        assert result["id"] == 42
        assert result["status"] == "pending"
        assert result["importance_score"] == 0.5


# ---------------------------------------------------------------------------
# Tests: capture_candidate
# ---------------------------------------------------------------------------


class TestCaptureCandidate:
    def test_returns_none_for_empty_text(self, mock_indexer, mock_persistence):
        svc = MemoryService(db_engine=FakeEngine(), indexer=mock_indexer)
        assert svc.capture_candidate("user1", "sess1", "") is None

    def test_returns_none_when_no_engine(self, mock_indexer, mock_persistence):
        svc = MemoryService(db_engine=MagicMock(__bool__=lambda s: False), indexer=mock_indexer)
        svc.engine = None
        assert svc.capture_candidate("user1", "sess1", "some text") is None

    def test_truncates_text_to_max_chars(self, mock_indexer, mock_persistence):
        long_text = "x" * 2000
        fake_conn = FakeConnection(results=[
            FakeResult([FakeRow(1, "2024-01-01")])
        ])
        svc = MemoryService(db_engine=FakeEngine(connection=fake_conn), indexer=mock_indexer)
        result = svc.capture_candidate("user1", "sess1", long_text)
        assert result is not None
        assert len(result["candidate_text"]) == MAX_EXPLICIT_MEMORY_CHARS


# ---------------------------------------------------------------------------
# Tests: save_explicit_memory
# ---------------------------------------------------------------------------


class TestSaveExplicitMemory:
    def test_returns_none_for_empty_text(self, mock_indexer, mock_persistence):
        svc = MemoryService(db_engine=FakeEngine(), indexer=mock_indexer)
        assert svc.save_explicit_memory("user1", "sess1", "") is None

    def test_saves_to_core_memories_and_indexes(self, mock_indexer, mock_persistence):
        fake_conn = FakeConnection(results=[
            FakeResult([FakeRow(99, "2024-06-15T12:00:00")])
        ])
        svc = MemoryService(db_engine=FakeEngine(connection=fake_conn), indexer=mock_indexer)
        result = svc.save_explicit_memory("user1", "sess1", "My favorite color is blue")
        assert result is not None
        assert result["id"] == 99
        assert result["fact"] == "My favorite color is blue"
        assert result["category"] == "general"
        mock_indexer.add_fact.assert_called_once_with("My favorite color is blue")

    def test_truncates_to_1000_chars(self, mock_indexer, mock_persistence):
        long_fact = "a" * 1500
        fake_conn = FakeConnection(results=[
            FakeResult([FakeRow(1, "2024-01-01")])
        ])
        svc = MemoryService(db_engine=FakeEngine(connection=fake_conn), indexer=mock_indexer)
        result = svc.save_explicit_memory("user1", None, long_fact)
        assert result is not None
        assert len(result["fact"]) == MAX_EXPLICIT_MEMORY_CHARS


# ---------------------------------------------------------------------------
# Tests: approve_candidate
# ---------------------------------------------------------------------------


class TestApproveCandidate:
    def test_returns_none_when_candidate_not_found(self, mock_indexer, mock_persistence):
        fake_conn = FakeConnection(results=[FakeResult([])])
        svc = MemoryService(db_engine=FakeEngine(connection=fake_conn), indexer=mock_indexer)
        assert svc.approve_candidate(999) is None

    def test_returns_none_when_not_pending(self, mock_indexer, mock_persistence):
        fake_conn = FakeConnection(results=[
            FakeResult([FakeRow(1, "user1", "sess1", "some fact", "approved")])
        ])
        svc = MemoryService(db_engine=FakeEngine(connection=fake_conn), indexer=mock_indexer)
        assert svc.approve_candidate(1) is None

    def test_promotes_pending_candidate(self, mock_indexer, mock_persistence):
        fake_conn = FakeConnection(results=[
            # First query: fetch candidate
            FakeResult([FakeRow(1, "user1", "sess1", "important fact", "pending")]),
            # Second query: update candidate status
            FakeResult([]),
            # Third query: insert into core_memories
            FakeResult([FakeRow(50, "2024-01-01")]),
        ])
        svc = MemoryService(db_engine=FakeEngine(connection=fake_conn), indexer=mock_indexer)
        result = svc.approve_candidate(1)
        assert result is not None
        assert result["status"] == "approved"
        assert result["core_memory_id"] == 50
        assert result["fact"] == "important fact"
        mock_indexer.add_fact.assert_called_once_with("important fact")


# ---------------------------------------------------------------------------
# Tests: reject_candidate
# ---------------------------------------------------------------------------


class TestRejectCandidate:
    def test_returns_none_when_not_found(self, mock_indexer, mock_persistence):
        fake_conn = FakeConnection(results=[FakeResult([])])
        svc = MemoryService(db_engine=FakeEngine(connection=fake_conn), indexer=mock_indexer)
        assert svc.reject_candidate(999) is None

    def test_marks_candidate_as_rejected(self, mock_indexer, mock_persistence):
        fake_conn = FakeConnection(results=[
            FakeResult([FakeRow(5, "user1", "a pending fact")])
        ])
        svc = MemoryService(db_engine=FakeEngine(connection=fake_conn), indexer=mock_indexer)
        result = svc.reject_candidate(5)
        assert result is not None
        assert result["status"] == "rejected"
        assert result["id"] == 5


# ---------------------------------------------------------------------------
# Tests: search_memory
# ---------------------------------------------------------------------------


class TestSearchMemory:
    def test_returns_empty_for_empty_query(self, mock_indexer, mock_persistence):
        svc = MemoryService(db_engine=FakeEngine(), indexer=mock_indexer)
        result = svc.search_memory("user1", "")
        assert result.memories == []
        assert result.metadata.pipeline == "empty_query"

    def test_uses_indexer_for_hybrid_search(self, mock_indexer, mock_persistence):
        svc = MemoryService(db_engine=FakeEngine(), indexer=mock_indexer)
        result = svc.search_memory("user1", "what is my name")
        assert len(result.memories) == 3
        assert result.metadata.pipeline == "hybrid"
        assert result.metadata.retrieved_count == 3
        assert result.metadata.latency_ms >= 0

    def test_respects_char_budget(self, mock_indexer, mock_persistence):
        # Return facts that together exceed a budget of 250
        mock_indexer.search_facts.return_value = ["a" * 200, "b" * 200, "c" * 200]
        svc = MemoryService(db_engine=FakeEngine(), indexer=mock_indexer)
        result = svc.search_memory("user1", "test", char_budget=250)
        # Total chars should not exceed the char_budget (250)
        total_chars = sum(len(m["fact"]) for m in result.memories)
        assert total_chars <= 250

    def test_falls_back_to_fts_when_indexer_disabled(self, mock_persistence):
        disabled_indexer = MagicMock()
        disabled_indexer.enabled = False
        fake_conn = FakeConnection(results=[
            FakeResult([FakeRow("fallback fact")])
        ])
        svc = MemoryService(db_engine=FakeEngine(connection=fake_conn), indexer=disabled_indexer)
        result = svc.search_memory("user1", "test")
        assert result.metadata.pipeline == "fts_only"

    def test_returns_retrieval_metadata(self, mock_indexer, mock_persistence):
        svc = MemoryService(db_engine=FakeEngine(), indexer=mock_indexer)
        result = svc.search_memory("user1", "query")
        meta = result.metadata
        assert isinstance(meta.retrieved_count, int)
        assert isinstance(meta.context_chars, int)
        assert isinstance(meta.pipeline, str)
        assert isinstance(meta.latency_ms, int)


# ---------------------------------------------------------------------------
# Tests: forget_memory
# ---------------------------------------------------------------------------


class TestForgetMemory:
    def test_returns_false_when_not_found(self, mock_indexer, mock_persistence):
        fake_conn = FakeConnection(results=[FakeResult([])])
        svc = MemoryService(db_engine=FakeEngine(connection=fake_conn), indexer=mock_indexer)
        assert svc.forget_memory("user1", 999) is False

    def test_deletes_existing_memory(self, mock_indexer, mock_persistence):
        fake_conn = FakeConnection(results=[
            FakeResult([FakeRow("some fact")]),  # SELECT
            FakeResult([]),  # DELETE
        ])
        svc = MemoryService(db_engine=FakeEngine(connection=fake_conn), indexer=mock_indexer)
        assert svc.forget_memory("user1", 1) is True

    def test_returns_false_when_no_engine(self, mock_indexer, mock_persistence):
        svc = MemoryService(db_engine=MagicMock(__bool__=lambda s: False), indexer=mock_indexer)
        svc.engine = None
        assert svc.forget_memory("user1", 1) is False


# ---------------------------------------------------------------------------
# Tests: _compress_to_budget
# ---------------------------------------------------------------------------


class TestCompressToBudget:
    def test_empty_facts(self, mock_indexer, mock_persistence):
        svc = MemoryService(db_engine=FakeEngine(), indexer=mock_indexer)
        assert svc._compress_to_budget([], 1200) == []

    def test_all_facts_fit(self, mock_indexer, mock_persistence):
        svc = MemoryService(db_engine=FakeEngine(), indexer=mock_indexer)
        facts = ["short fact", "another fact"]
        result = svc._compress_to_budget(facts, 1200)
        assert len(result) == 2
        assert result[0]["fact"] == "short fact"
        assert result[1]["fact"] == "another fact"

    def test_truncates_when_over_budget(self, mock_indexer, mock_persistence):
        svc = MemoryService(db_engine=FakeEngine(), indexer=mock_indexer)
        facts = ["a" * 100, "b" * 100]
        result = svc._compress_to_budget(facts, 120)
        # First fact fits (100 chars), second gets truncated to fit within remaining 20
        assert len(result) == 2
        total = sum(len(m["fact"]) for m in result)
        assert total <= 120

    def test_drops_excess_facts(self, mock_indexer, mock_persistence):
        svc = MemoryService(db_engine=FakeEngine(), indexer=mock_indexer)
        facts = ["a" * 50, "b" * 50, "c" * 50]
        result = svc._compress_to_budget(facts, 80)
        # Only first fact fits fully (50), second partially (30+...)
        assert len(result) == 2
