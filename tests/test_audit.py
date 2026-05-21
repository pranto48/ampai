"""Tests for core/audit.py — AuditLogger class.

Validates append-only insert, query with filters, error resilience,
details truncation, and action type constants.
"""

from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch, call
from contextlib import contextmanager

import pytest

from core.audit import (
    AuditLogger,
    ACTION_MEMORY_WRITE,
    ACTION_MEMORY_READ,
    ACTION_MEMORY_DELETE,
    ACTION_BROWSER_ACTION,
    ACTION_BROWSER_NAVIGATE,
    ACTION_TERMINAL_EXECUTE,
    ACTION_TERMINAL_BLOCKED,
    ACTION_TELEGRAM_MESSAGE,
    ACTION_BACKUP_RUN,
    ACTION_BACKUP_RESTORE,
    ACTION_LOGIN_ATTEMPT,
    ACTION_WEB_SEARCH,
    ACTION_CONFIG_CHANGE,
    ALL_ACTION_TYPES,
    MAX_DETAILS_CHARS,
    MAX_QUERY_LIMIT,
    DEFAULT_QUERY_LIMIT,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_engine():
    """Create a mock SQLAlchemy engine with a working begin() context manager."""
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


@pytest.fixture
def audit_logger(mock_engine):
    engine, _ = mock_engine
    return AuditLogger(engine)


# ---------------------------------------------------------------------------
# Action type constants
# ---------------------------------------------------------------------------


class TestActionTypeConstants:
    """Verify all required action type constants are defined."""

    def test_memory_write(self):
        assert ACTION_MEMORY_WRITE == "memory_write"

    def test_memory_read(self):
        assert ACTION_MEMORY_READ == "memory_read"

    def test_memory_delete(self):
        assert ACTION_MEMORY_DELETE == "memory_delete"

    def test_browser_action(self):
        assert ACTION_BROWSER_ACTION == "browser_action"

    def test_browser_navigate(self):
        assert ACTION_BROWSER_NAVIGATE == "browser_navigate"

    def test_terminal_execute(self):
        assert ACTION_TERMINAL_EXECUTE == "terminal_execute"

    def test_terminal_blocked(self):
        assert ACTION_TERMINAL_BLOCKED == "terminal_blocked"

    def test_telegram_message(self):
        assert ACTION_TELEGRAM_MESSAGE == "telegram_message"

    def test_backup_run(self):
        assert ACTION_BACKUP_RUN == "backup_run"

    def test_backup_restore(self):
        assert ACTION_BACKUP_RESTORE == "backup_restore"

    def test_login_attempt(self):
        assert ACTION_LOGIN_ATTEMPT == "login_attempt"

    def test_web_search(self):
        assert ACTION_WEB_SEARCH == "web_search"

    def test_config_change(self):
        assert ACTION_CONFIG_CHANGE == "config_change"

    def test_all_action_types_tuple(self):
        assert len(ALL_ACTION_TYPES) == 13
        assert ACTION_MEMORY_WRITE in ALL_ACTION_TYPES
        assert ACTION_CONFIG_CHANGE in ALL_ACTION_TYPES


# ---------------------------------------------------------------------------
# AuditLogger.log()
# ---------------------------------------------------------------------------


class TestAuditLoggerLog:
    """Tests for the log() method — append-only insert."""

    def test_log_basic_event(self, mock_engine):
        engine, conn = mock_engine
        audit = AuditLogger(engine)

        audit.log(
            username="alice",
            action_type=ACTION_MEMORY_WRITE,
            details={"fact": "likes coffee"},
            session_id="sess-123",
            category="memory",
        )

        conn.execute.assert_called_once()
        call_args = conn.execute.call_args
        params = call_args[0][1]
        assert params["username"] == "alice"
        assert params["action_type"] == "memory_write"
        assert params["session_id"] == "sess-123"
        assert params["category"] == "memory"
        assert '"likes coffee"' in params["details"]

    def test_log_without_optional_fields(self, mock_engine):
        engine, conn = mock_engine
        audit = AuditLogger(engine)

        audit.log(username="bob", action_type=ACTION_LOGIN_ATTEMPT)

        conn.execute.assert_called_once()
        params = conn.execute.call_args[0][1]
        assert params["username"] == "bob"
        assert params["action_type"] == "login_attempt"
        assert params["session_id"] is None
        assert params["category"] is None
        assert params["details"] is None

    def test_log_truncates_details_to_max_chars(self, mock_engine):
        engine, conn = mock_engine
        audit = AuditLogger(engine)

        # Create details that serialize to more than MAX_DETAILS_CHARS
        long_value = "x" * 3000
        audit.log(
            username="alice",
            action_type=ACTION_TERMINAL_EXECUTE,
            details={"output": long_value},
        )

        conn.execute.assert_called_once()
        params = conn.execute.call_args[0][1]
        assert len(params["details"]) <= MAX_DETAILS_CHARS

    def test_log_failure_does_not_raise(self, mock_engine):
        """Requirement 15.7: If audit logging fails, continue original operation."""
        engine, conn = mock_engine
        conn.execute.side_effect = Exception("DB connection lost")
        audit = AuditLogger(engine)

        # Should NOT raise
        audit.log(username="alice", action_type=ACTION_MEMORY_WRITE)

    def test_log_failure_logs_error(self, mock_engine, caplog):
        """Requirement 15.7: Log failure to application error log."""
        engine, conn = mock_engine
        conn.execute.side_effect = Exception("DB connection lost")
        audit = AuditLogger(engine)

        import logging
        with caplog.at_level(logging.ERROR):
            audit.log(username="alice", action_type=ACTION_MEMORY_WRITE)

        assert "Failed to write audit event" in caplog.text

    def test_log_with_none_details(self, mock_engine):
        engine, conn = mock_engine
        audit = AuditLogger(engine)

        audit.log(username="alice", action_type=ACTION_WEB_SEARCH, details=None)

        params = conn.execute.call_args[0][1]
        assert params["details"] is None


# ---------------------------------------------------------------------------
# AuditLogger.query()
# ---------------------------------------------------------------------------


class TestAuditLoggerQuery:
    """Tests for the query() method — filtered reads."""

    def test_query_no_filters(self, mock_engine):
        engine, conn = mock_engine
        conn.execute.return_value.mappings.return_value.all.return_value = []
        audit = AuditLogger(engine)

        result = audit.query()

        assert result == []
        conn.execute.assert_called_once()
        sql_text = str(conn.execute.call_args[0][0])
        assert "FROM audit_events" in sql_text
        assert "ORDER BY created_at DESC" in sql_text

    def test_query_with_action_type_filter(self, mock_engine):
        engine, conn = mock_engine
        conn.execute.return_value.mappings.return_value.all.return_value = []
        audit = AuditLogger(engine)

        audit.query(action_type=ACTION_MEMORY_WRITE)

        sql_text = str(conn.execute.call_args[0][0])
        assert "action_type = :action_type" in sql_text

    def test_query_with_username_filter(self, mock_engine):
        engine, conn = mock_engine
        conn.execute.return_value.mappings.return_value.all.return_value = []
        audit = AuditLogger(engine)

        audit.query(username="alice")

        sql_text = str(conn.execute.call_args[0][0])
        assert "username = :username" in sql_text

    def test_query_with_date_range(self, mock_engine):
        engine, conn = mock_engine
        conn.execute.return_value.mappings.return_value.all.return_value = []
        audit = AuditLogger(engine)

        now = datetime.now(timezone.utc)
        audit.query(date_from=now - timedelta(days=7), date_to=now)

        sql_text = str(conn.execute.call_args[0][0])
        assert "created_at >= :date_from" in sql_text
        assert "created_at <= :date_to" in sql_text

    def test_query_with_session_id_filter(self, mock_engine):
        engine, conn = mock_engine
        conn.execute.return_value.mappings.return_value.all.return_value = []
        audit = AuditLogger(engine)

        audit.query(session_id="sess-456")

        sql_text = str(conn.execute.call_args[0][0])
        assert "session_id = :session_id" in sql_text

    def test_query_caps_limit_at_max(self, mock_engine):
        engine, conn = mock_engine
        conn.execute.return_value.mappings.return_value.all.return_value = []
        audit = AuditLogger(engine)

        audit.query(limit=5000)

        params = conn.execute.call_args[0][1]
        assert params["limit"] == MAX_QUERY_LIMIT

    def test_query_uses_default_limit(self, mock_engine):
        engine, conn = mock_engine
        conn.execute.return_value.mappings.return_value.all.return_value = []
        audit = AuditLogger(engine)

        audit.query()

        params = conn.execute.call_args[0][1]
        assert params["limit"] == DEFAULT_QUERY_LIMIT

    def test_query_negative_limit_uses_default(self, mock_engine):
        engine, conn = mock_engine
        conn.execute.return_value.mappings.return_value.all.return_value = []
        audit = AuditLogger(engine)

        audit.query(limit=-1)

        params = conn.execute.call_args[0][1]
        assert params["limit"] == DEFAULT_QUERY_LIMIT

    def test_query_negative_offset_uses_zero(self, mock_engine):
        engine, conn = mock_engine
        conn.execute.return_value.mappings.return_value.all.return_value = []
        audit = AuditLogger(engine)

        audit.query(offset=-5)

        params = conn.execute.call_args[0][1]
        assert params["offset"] == 0

    def test_query_returns_formatted_results(self, mock_engine):
        engine, conn = mock_engine
        now = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        mock_row = {
            "id": 1,
            "username": "alice",
            "action_type": "memory_write",
            "session_id": "sess-1",
            "category": "memory",
            "details": {"fact": "test"},
            "created_at": now,
        }
        conn.execute.return_value.mappings.return_value.all.return_value = [mock_row]
        audit = AuditLogger(engine)

        results = audit.query()

        assert len(results) == 1
        assert results[0]["id"] == 1
        assert results[0]["username"] == "alice"
        assert results[0]["action_type"] == "memory_write"
        assert results[0]["created_at"] == now.isoformat()

    def test_query_failure_returns_empty_list(self, mock_engine):
        """Query errors should not propagate — return empty list."""
        engine, conn = mock_engine
        conn.execute.side_effect = Exception("DB error")
        audit = AuditLogger(engine)

        result = audit.query()

        assert result == []

    def test_query_with_all_filters(self, mock_engine):
        engine, conn = mock_engine
        conn.execute.return_value.mappings.return_value.all.return_value = []
        audit = AuditLogger(engine)

        now = datetime.now(timezone.utc)
        audit.query(
            action_type=ACTION_BROWSER_NAVIGATE,
            username="bob",
            date_from=now - timedelta(days=1),
            date_to=now,
            session_id="sess-789",
            limit=50,
            offset=10,
        )

        sql_text = str(conn.execute.call_args[0][0])
        assert "action_type = :action_type" in sql_text
        assert "username = :username" in sql_text
        assert "created_at >= :date_from" in sql_text
        assert "created_at <= :date_to" in sql_text
        assert "session_id = :session_id" in sql_text
        params = conn.execute.call_args[0][1]
        assert params["limit"] == 50
        assert params["offset"] == 10
