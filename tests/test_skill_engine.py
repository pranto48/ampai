"""Tests for skill_engine.py — Skill detection, CRUD, safety levels, approval, and metrics.

Validates Requirements 14.1-14.6:
- Pattern detection (3+ sessions in 30-day window)
- User/admin approval before activation
- Safety levels: read-only, write, privileged
- Failure handling: halt skill, preserve pre-execution state
- Rejection tracking
- Metrics endpoint
"""

import sys
import os
from unittest.mock import MagicMock, patch
from contextlib import contextmanager

import pytest

# ---------------------------------------------------------------------------
# Mock heavy dependencies before importing skill_engine
# ---------------------------------------------------------------------------

# Save the real sqlalchemy module before any mocking
_real_sqlalchemy_module = sys.modules.get("sqlalchemy")

# Create mock modules for dependencies that require DB/LLM
mock_database = MagicMock()
mock_database.engine = None  # Will be overridden per test
mock_database.get_config = MagicMock(return_value=None)

# Patch sys.modules before importing skill_engine
sys.modules.setdefault("langchain_community", MagicMock())
sys.modules.setdefault("langchain_community.chat_message_histories", MagicMock())
sys.modules.setdefault("langchain_core", MagicMock())
sys.modules.setdefault("langchain_core.messages", MagicMock())
sys.modules.setdefault("pgvector", MagicMock())
sys.modules.setdefault("pgvector.sqlalchemy", MagicMock())

# Now we need to handle the database import specially
# We'll mock it at the module level
_original_database = sys.modules.get("database")
sys.modules["database"] = mock_database

# Now import with proper sqlalchemy.text
import importlib
import importlib.util

# Load skill_engine with mocked dependencies
_skill_engine_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "skill_engine.py",
)

# We need to handle the `from sqlalchemy import text` import
# Let's just patch and import
with patch.dict(sys.modules, {
    "database": mock_database,
}):
    # Force reimport
    if "skill_engine" in sys.modules:
        del sys.modules["skill_engine"]

    # Create a proper sqlalchemy mock with text function
    import types
    sqlalchemy_mock = types.ModuleType("sqlalchemy")
    sqlalchemy_mock.text = lambda x: x  # text() just returns the string

    with patch.dict(sys.modules, {"sqlalchemy": sqlalchemy_mock}):
        # Load the module
        spec = importlib.util.spec_from_file_location("skill_engine", _skill_engine_path)
        skill_engine = importlib.util.module_from_spec(spec)
        sys.modules["skill_engine"] = skill_engine
        # The module will try to call _ensure_skill_tables on import, which needs engine
        mock_database.engine = None  # Disable during import
        spec.loader.exec_module(skill_engine)

# Restore the real sqlalchemy module to prevent pollution of other tests
if _real_sqlalchemy_module is not None:
    sys.modules["sqlalchemy"] = _real_sqlalchemy_module
    # Also clean up any corrupted sub-modules
    _corrupted_sa_keys = [k for k in list(sys.modules.keys())
                          if k.startswith("sqlalchemy.") and isinstance(sys.modules[k], MagicMock)]
    for _k in _corrupted_sa_keys:
        del sys.modules[_k]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_engine():
    """Create a mock SQLAlchemy engine."""
    engine = MagicMock()
    conn = MagicMock()

    @contextmanager
    def begin_ctx():
        yield conn

    @contextmanager
    def connect_ctx():
        yield conn

    engine.begin = begin_ctx
    engine.connect = connect_ctx
    return engine, conn


# ---------------------------------------------------------------------------
# Safety Level Determination (Requirement 14.3)
# ---------------------------------------------------------------------------


class TestDetermineSafetyLevel:
    """Tests for determine_safety_level function."""

    def test_read_only_for_simple_retrieval(self):
        result = skill_engine.determine_safety_level("Retrieve user preferences and display them")
        assert result == "read-only"

    def test_write_for_modification_actions(self):
        result = skill_engine.determine_safety_level("Create a new task and update the user's schedule")
        assert result == "write"

    def test_privileged_for_browser_actions(self):
        result = skill_engine.determine_safety_level("Navigate to the website and click the submit button")
        assert result == "privileged"

    def test_privileged_for_terminal_actions(self):
        result = skill_engine.determine_safety_level("Execute a shell command to check disk usage")
        assert result == "privileged"

    def test_privileged_from_tool_requirements(self):
        result = skill_engine.determine_safety_level("Do something", tool_requirements=["browser"])
        assert result == "privileged"

    def test_write_from_tool_requirements(self):
        result = skill_engine.determine_safety_level("Do something", tool_requirements=["tasks"])
        assert result == "write"

    def test_read_only_for_empty_prompt(self):
        result = skill_engine.determine_safety_level("")
        assert result == "read-only"


# ---------------------------------------------------------------------------
# Approval Workflow (Requirement 14.2)
# ---------------------------------------------------------------------------


class TestApprovalWorkflow:
    """Tests for skill approval and rejection."""

    def test_approve_skill_updates_status(self, mock_engine):
        engine, conn = mock_engine
        conn.execute.return_value.rowcount = 1

        skill_engine.engine = engine
        try:
            result = skill_engine.approve_skill(1, approved_by="admin")
            assert result is True
        finally:
            skill_engine.engine = None

    def test_approve_skill_no_engine(self):
        skill_engine.engine = None
        result = skill_engine.approve_skill(1, approved_by="admin")
        assert result is False

    def test_reject_skill_suggestion_records_rejection(self, mock_engine):
        engine, conn = mock_engine
        # Mock getting the skill
        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, idx: {0: "test_hash", 1: "Test Skill"}[idx]
        conn.execute.return_value.fetchone.return_value = mock_row

        skill_engine.engine = engine
        try:
            result = skill_engine.reject_skill_suggestion(
                skill_id=1,
                rejected_by="user1",
                reason="Not useful",
            )
            assert result is True
        finally:
            skill_engine.engine = None

    def test_reject_skill_no_engine(self):
        skill_engine.engine = None
        result = skill_engine.reject_skill_suggestion(
            pattern_hash="abc123",
            rejected_by="user1",
        )
        assert result is False


# ---------------------------------------------------------------------------
# Skill Execution with Safety Checks (Requirements 14.2, 14.3, 14.4)
# ---------------------------------------------------------------------------


class TestSkillExecution:
    """Tests for run_skill with approval and safety level enforcement."""

    def test_unapproved_skill_blocked(self, mock_engine):
        engine, conn = mock_engine
        mock_skill = {
            "id": 1,
            "name": "Test Skill",
            "description": "test",
            "system_prompt": "do something",
            "safety_level": "read-only",
            "approval_status": "pending_approval",
        }

        skill_engine.engine = engine
        try:
            with patch.object(skill_engine, "get_skill", return_value=mock_skill):
                result = skill_engine.run_skill(skill_id=1, user_message="hello")
                assert result["outcome"] == "blocked"
                assert "not been approved" in result["error"]
        finally:
            skill_engine.engine = None

    def test_write_skill_requires_confirmation(self, mock_engine):
        engine, conn = mock_engine
        mock_skill = {
            "id": 1,
            "name": "Write Skill",
            "description": "modifies data",
            "system_prompt": "create task",
            "safety_level": "write",
            "approval_status": "approved",
        }

        skill_engine.engine = engine
        try:
            with patch.object(skill_engine, "get_skill", return_value=mock_skill):
                result = skill_engine.run_skill(skill_id=1, user_message="hello", confirmed=False)
                assert result["outcome"] == "confirmation_required"
                assert result["safety_level"] == "write"
        finally:
            skill_engine.engine = None

    def test_privileged_skill_requires_confirmation(self, mock_engine):
        engine, conn = mock_engine
        mock_skill = {
            "id": 1,
            "name": "Privileged Skill",
            "description": "runs commands",
            "system_prompt": "execute terminal command",
            "safety_level": "privileged",
            "approval_status": "approved",
        }

        skill_engine.engine = engine
        try:
            with patch.object(skill_engine, "get_skill", return_value=mock_skill):
                result = skill_engine.run_skill(skill_id=1, user_message="hello", confirmed=False)
                assert result["outcome"] == "confirmation_required"
                assert result["safety_level"] == "privileged"
        finally:
            skill_engine.engine = None

    def test_skill_not_found(self, mock_engine):
        engine, conn = mock_engine

        skill_engine.engine = engine
        try:
            with patch.object(skill_engine, "get_skill", return_value=None):
                result = skill_engine.run_skill(skill_id=999, user_message="hello")
                assert result["outcome"] == "failure"
                assert "not found" in result["error"]
        finally:
            skill_engine.engine = None


# ---------------------------------------------------------------------------
# Pattern Detection (Requirement 14.1)
# ---------------------------------------------------------------------------


class TestPatternDetection:
    """Tests for detect_repeated_patterns."""

    def test_no_engine_returns_empty(self):
        skill_engine.engine = None
        result = skill_engine.detect_repeated_patterns(username="user1")
        assert result == []

    def test_detects_patterns_with_3_plus_sessions(self, mock_engine):
        engine, conn = mock_engine

        # First call: category query returns results
        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, idx: {
            0: "Code Review",
            1: 4,
            2: ["sess-1", "sess-2", "sess-3", "sess-4"],
        }[idx]

        # Set up the execute mock to return different results for different queries
        call_count = [0]

        def mock_execute(*args, **kwargs):
            call_count[0] += 1
            result = MagicMock()
            if call_count[0] == 1:
                # First call: category query
                result.fetchall.return_value = [mock_row]
            elif call_count[0] == 2:
                # Second call: rejection check
                result.fetchone.return_value = None  # Not rejected
            elif call_count[0] == 3:
                # Third call: existing skill check
                result.fetchone.return_value = None  # No existing skill
            return result

        conn.execute.side_effect = mock_execute

        skill_engine.engine = engine
        try:
            result = skill_engine.detect_repeated_patterns(username="user1", min_occurrences=3)
            assert len(result) == 1
            assert result[0]["pattern_description"] == "Code Review"
            assert result[0]["session_count"] == 4
        finally:
            skill_engine.engine = None


# ---------------------------------------------------------------------------
# Rejection Tracking (Requirement 14.6)
# ---------------------------------------------------------------------------


class TestRejectionTracking:
    """Tests for rejection tracking."""

    def test_is_pattern_rejected_true(self, mock_engine):
        engine, conn = mock_engine
        conn.execute.return_value.fetchone.return_value = MagicMock()  # Row exists

        skill_engine.engine = engine
        try:
            result = skill_engine.is_pattern_rejected("abc123")
            assert result is True
        finally:
            skill_engine.engine = None

    def test_is_pattern_rejected_false(self, mock_engine):
        engine, conn = mock_engine
        conn.execute.return_value.fetchone.return_value = None  # No row

        skill_engine.engine = engine
        try:
            result = skill_engine.is_pattern_rejected("abc123")
            assert result is False
        finally:
            skill_engine.engine = None

    def test_clear_pattern_rejection(self, mock_engine):
        engine, conn = mock_engine

        skill_engine.engine = engine
        try:
            result = skill_engine.clear_pattern_rejection("abc123")
            assert result is True
            conn.execute.assert_called()
        finally:
            skill_engine.engine = None

    def test_clear_pattern_rejection_no_engine(self):
        skill_engine.engine = None
        result = skill_engine.clear_pattern_rejection("abc123")
        assert result is False


# ---------------------------------------------------------------------------
# Metrics (Requirement 14.5)
# ---------------------------------------------------------------------------


class TestSkillMetrics:
    """Tests for get_skill_metrics."""

    def test_metrics_with_runs(self, mock_engine):
        engine, conn = mock_engine
        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, idx: {
            0: 10,    # invocation_count
            1: 8,     # successes
            2: 150.5, # avg_latency
            3: "2024-01-15 12:00:00",  # last_execution
            4: "2024-01-01 10:00:00",  # first_execution
        }[idx]
        conn.execute.return_value.fetchone.return_value = mock_row

        skill_engine.engine = engine
        try:
            metrics = skill_engine.get_skill_metrics(1)
            assert metrics["invocation_count"] == 10
            assert metrics["success_rate"] == 0.8
            assert metrics["avg_execution_duration_ms"] == 150.5
        finally:
            skill_engine.engine = None

    def test_metrics_no_runs(self, mock_engine):
        engine, conn = mock_engine
        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, idx: {
            0: 0,     # invocation_count
            1: 0,     # successes
            2: None,  # avg_latency
            3: None,  # last_execution
            4: None,  # first_execution
        }[idx]
        conn.execute.return_value.fetchone.return_value = mock_row

        skill_engine.engine = engine
        try:
            metrics = skill_engine.get_skill_metrics(1)
            assert metrics["invocation_count"] == 0
            assert metrics["success_rate"] == 0.0
            assert metrics["avg_execution_duration_ms"] == 0.0
        finally:
            skill_engine.engine = None

    def test_metrics_no_engine(self):
        skill_engine.engine = None
        metrics = skill_engine.get_skill_metrics(1)
        assert metrics["invocation_count"] == 0
        assert metrics["success_rate"] == 0.0


# ---------------------------------------------------------------------------
# Pattern Hash Computation
# ---------------------------------------------------------------------------


class TestPatternHash:
    """Tests for _compute_pattern_hash."""

    def test_consistent_hash(self):
        hash1 = skill_engine._compute_pattern_hash("Code Review")
        hash2 = skill_engine._compute_pattern_hash("Code Review")
        assert hash1 == hash2

    def test_case_insensitive(self):
        hash1 = skill_engine._compute_pattern_hash("Code Review")
        hash2 = skill_engine._compute_pattern_hash("code review")
        assert hash1 == hash2

    def test_strips_whitespace(self):
        hash1 = skill_engine._compute_pattern_hash("Code Review")
        hash2 = skill_engine._compute_pattern_hash("  Code Review  ")
        assert hash1 == hash2

    def test_different_patterns_different_hashes(self):
        hash1 = skill_engine._compute_pattern_hash("Code Review")
        hash2 = skill_engine._compute_pattern_hash("Bug Fix")
        assert hash1 != hash2


# ---------------------------------------------------------------------------
# Safety Level Constants
# ---------------------------------------------------------------------------


class TestSafetyLevelConstants:
    """Verify safety level constants are properly defined."""

    def test_safety_levels_tuple(self):
        assert "read-only" in skill_engine.SAFETY_LEVELS
        assert "write" in skill_engine.SAFETY_LEVELS
        assert "privileged" in skill_engine.SAFETY_LEVELS
        assert len(skill_engine.SAFETY_LEVELS) == 3

    def test_approval_constants(self):
        assert skill_engine.APPROVAL_PENDING == "pending_approval"
        assert skill_engine.APPROVAL_APPROVED == "approved"
        assert skill_engine.APPROVAL_REJECTED == "rejected"
