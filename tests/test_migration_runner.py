"""Tests for migration_runner module.

Validates the MigrationRunner class including:
- Registration and execution of migrations
- _migrations tracking table creation
- Rollback on failure behavior
- Connection retry logic
- Timeout enforcement
- Additive-only (IF NOT EXISTS) patterns

Requirements: 3.1, 3.2, 3.5, 3.6, 3.7
"""

import time
import types as _types
from unittest.mock import MagicMock, patch, call

import pytest

# Ensure we have the real sqlalchemy module (other tests may have mocked it in sys.modules)
import sys
from unittest.mock import MagicMock as _MM

if "sqlalchemy" in sys.modules:
    _sa = sys.modules["sqlalchemy"]
    # Detect if sqlalchemy was replaced by a mock or a bare types.ModuleType stub
    if isinstance(_sa, _MM) or (isinstance(_sa, _types.ModuleType) and not hasattr(_sa, "create_engine")):
        # Remove corrupted sqlalchemy and all sub-modules
        _all_sa = [k for k in list(sys.modules.keys()) if k == "sqlalchemy" or k.startswith("sqlalchemy.")]
        for _k in _all_sa:
            del sys.modules[_k]
else:
    # Also remove any mocked sub-modules
    _sa_keys_to_remove = [k for k in list(sys.modules.keys())
                          if k.startswith("sqlalchemy") and isinstance(sys.modules.get(k), _MM)]
    for _k in _sa_keys_to_remove:
        del sys.modules[_k]

from sqlalchemy import create_engine, text, inspect

from migration_runner import (
    MigrationRunner,
    MigrationResult,
    MigrationTimeoutError,
    MigrationConnectionError,
    MigrationError,
)


@pytest.fixture
def sqlite_engine():
    """Create an in-memory SQLite engine for testing."""
    engine = create_engine("sqlite:///:memory:")
    return engine


@pytest.fixture
def runner(sqlite_engine):
    """Create a MigrationRunner with an in-memory SQLite engine."""
    return MigrationRunner(sqlite_engine)


class TestMigrationRegistration:
    """Tests for migration registration."""

    def test_register_single_migration(self, runner):
        @runner.register(1, "create_users")
        def migrate_v1(conn):
            pass

        assert len(runner._migrations) == 1
        assert runner._migrations[0][0] == 1
        assert runner._migrations[0][1] == "create_users"

    def test_register_multiple_migrations_sorted(self, runner):
        @runner.register(3, "third")
        def migrate_v3(conn):
            pass

        @runner.register(1, "first")
        def migrate_v1(conn):
            pass

        @runner.register(2, "second")
        def migrate_v2(conn):
            pass

        assert len(runner._migrations) == 3
        assert runner._migrations[0][0] == 1
        assert runner._migrations[1][0] == 2
        assert runner._migrations[2][0] == 3

    def test_register_returns_original_function(self, runner):
        @runner.register(1, "test")
        def my_migration(conn):
            """My docstring."""
            pass

        assert my_migration.__name__ == "my_migration"
        assert my_migration.__doc__ == "My docstring."


class TestMigrationsTableCreation:
    """Tests for _migrations tracking table."""

    def test_creates_migrations_table(self, runner, sqlite_engine):
        @runner.register(1, "dummy")
        def migrate_v1(conn):
            pass

        runner.run_pending()

        with sqlite_engine.connect() as conn:
            inspector = inspect(sqlite_engine)
            assert inspector.has_table("_migrations")

    def test_migrations_table_has_correct_columns(self, runner, sqlite_engine):
        @runner.register(1, "dummy")
        def migrate_v1(conn):
            pass

        runner.run_pending()

        with sqlite_engine.connect() as conn:
            inspector = inspect(sqlite_engine)
            columns = {col["name"] for col in inspector.get_columns("_migrations")}
            assert "version" in columns
            assert "name" in columns
            assert "applied_at" in columns


class TestRunPending:
    """Tests for run_pending execution."""

    def test_runs_pending_migrations(self, runner, sqlite_engine):
        @runner.register(1, "create_test_table")
        def migrate_v1(conn):
            conn.execute(text("CREATE TABLE IF NOT EXISTS test_table (id INTEGER PRIMARY KEY)"))

        results = runner.run_pending()

        assert len(results) == 1
        assert results[0].version == 1
        assert results[0].name == "create_test_table"
        assert results[0].success is True
        assert results[0].duration_ms >= 0

        # Verify table was created
        with sqlite_engine.connect() as conn:
            inspector = inspect(sqlite_engine)
            assert inspector.has_table("test_table")

    def test_skips_already_applied_migrations(self, runner, sqlite_engine):
        call_count = {"v1": 0}

        @runner.register(1, "create_test_table")
        def migrate_v1(conn):
            call_count["v1"] += 1
            conn.execute(text("CREATE TABLE IF NOT EXISTS test_table (id INTEGER PRIMARY KEY)"))

        # Run once
        runner.run_pending()
        assert call_count["v1"] == 1

        # Run again - should skip
        results = runner.run_pending()
        assert len(results) == 0
        assert call_count["v1"] == 1

    def test_runs_only_new_migrations(self, runner, sqlite_engine):
        @runner.register(1, "first")
        def migrate_v1(conn):
            conn.execute(text("CREATE TABLE IF NOT EXISTS t1 (id INTEGER PRIMARY KEY)"))

        runner.run_pending()

        @runner.register(2, "second")
        def migrate_v2(conn):
            conn.execute(text("CREATE TABLE IF NOT EXISTS t2 (id INTEGER PRIMARY KEY)"))

        results = runner.run_pending()
        assert len(results) == 1
        assert results[0].version == 2

    def test_returns_empty_list_when_no_pending(self, runner):
        results = runner.run_pending()
        assert results == []

    def test_marks_applied_after_success(self, runner, sqlite_engine):
        @runner.register(1, "test_migration")
        def migrate_v1(conn):
            conn.execute(text("CREATE TABLE IF NOT EXISTS t1 (id INTEGER PRIMARY KEY)"))

        runner.run_pending()

        with sqlite_engine.connect() as conn:
            result = conn.execute(text("SELECT version, name FROM _migrations")).fetchall()
            assert len(result) == 1
            assert result[0][0] == 1
            assert result[0][1] == "test_migration"


class TestRollbackOnFailure:
    """Tests for rollback behavior when a migration fails."""

    def test_rollback_on_migration_failure(self, runner, sqlite_engine):
        @runner.register(1, "good_migration")
        def migrate_v1(conn):
            conn.execute(text("CREATE TABLE IF NOT EXISTS good_table (id INTEGER PRIMARY KEY)"))

        @runner.register(2, "bad_migration")
        def migrate_v2(conn):
            # This will fail - invalid SQL
            conn.execute(text("INVALID SQL STATEMENT"))

        with pytest.raises(MigrationError):
            runner.run_pending()

        # Good migration should have been applied
        with sqlite_engine.connect() as conn:
            inspector = inspect(sqlite_engine)
            assert inspector.has_table("good_table")

            # Bad migration should NOT be recorded
            result = conn.execute(
                text("SELECT version FROM _migrations WHERE version = 2")
            ).fetchall()
            assert len(result) == 0

    def test_failed_migration_leaves_existing_data_unmodified(self, runner, sqlite_engine):
        # Pre-populate some data
        with sqlite_engine.connect() as conn:
            conn.execute(text("CREATE TABLE existing_data (id INTEGER PRIMARY KEY, value TEXT)"))
            conn.execute(text("INSERT INTO existing_data (id, value) VALUES (1, 'original')"))
            conn.commit()

        @runner.register(1, "failing_migration")
        def migrate_v1(conn):
            raise RuntimeError("Simulated failure")

        with pytest.raises(MigrationError):
            runner.run_pending()

        # Existing data should be unmodified
        with sqlite_engine.connect() as conn:
            result = conn.execute(text("SELECT value FROM existing_data WHERE id = 1")).fetchone()
            assert result[0] == "original"

    def test_migration_error_includes_details(self, runner):
        @runner.register(1, "failing")
        def migrate_v1(conn):
            raise ValueError("Something went wrong")

        with pytest.raises(MigrationError) as exc_info:
            runner.run_pending()

        assert "v1" in str(exc_info.value)
        assert "failing" in str(exc_info.value)
        assert "Something went wrong" in str(exc_info.value)


class TestTimeout:
    """Tests for migration timeout enforcement."""

    def test_timeout_raises_error(self, runner):
        @runner.register(1, "slow_migration")
        def migrate_v1(conn):
            time.sleep(0.5)

        with pytest.raises(MigrationTimeoutError):
            runner.run_pending(timeout_seconds=0.1)

    def test_timeout_error_message(self, runner):
        @runner.register(1, "first")
        def migrate_v1(conn):
            pass

        @runner.register(2, "slow")
        def migrate_v2(conn):
            time.sleep(0.5)

        with pytest.raises(MigrationTimeoutError) as exc_info:
            runner.run_pending(timeout_seconds=0.1)

        assert "timeout" in str(exc_info.value).lower()


class TestConnectionRetry:
    """Tests for connection retry logic."""

    def test_retries_on_connection_failure(self):
        """Test that connection is retried up to 3 times."""
        mock_engine = MagicMock()
        runner = MigrationRunner(mock_engine)

        # First two attempts fail, third succeeds
        mock_conn = MagicMock()
        mock_engine.connect.side_effect = [
            Exception("Connection refused"),
            Exception("Connection refused"),
            mock_conn,
        ]

        with patch("migration_runner.time.sleep") as mock_sleep:
            conn = runner._connect_with_retry()

        assert conn == mock_conn
        assert mock_engine.connect.call_count == 3
        assert mock_sleep.call_count == 2
        mock_sleep.assert_called_with(2)

    def test_raises_after_max_retries(self):
        """Test that MigrationConnectionError is raised after 3 failed attempts."""
        mock_engine = MagicMock()
        runner = MigrationRunner(mock_engine)

        mock_engine.connect.side_effect = Exception("Connection refused")

        with patch("migration_runner.time.sleep"):
            with pytest.raises(MigrationConnectionError) as exc_info:
                runner._connect_with_retry()

        assert "3 attempts" in str(exc_info.value)
        assert "Connection refused" in str(exc_info.value)
        assert mock_engine.connect.call_count == 3

    def test_succeeds_on_first_attempt(self):
        """Test that no retry delay occurs when first attempt succeeds."""
        mock_engine = MagicMock()
        runner = MigrationRunner(mock_engine)

        mock_conn = MagicMock()
        mock_engine.connect.return_value = mock_conn

        with patch("migration_runner.time.sleep") as mock_sleep:
            conn = runner._connect_with_retry()

        assert conn == mock_conn
        assert mock_engine.connect.call_count == 1
        mock_sleep.assert_not_called()


class TestGetAppliedVersions:
    """Tests for _get_applied_versions."""

    def test_returns_empty_set_initially(self, runner, sqlite_engine):
        with sqlite_engine.connect() as conn:
            runner._ensure_migrations_table(conn)
            conn.commit()
            versions = runner._get_applied_versions(conn)

        assert versions == set()

    def test_returns_applied_versions(self, runner, sqlite_engine):
        @runner.register(1, "first")
        def migrate_v1(conn):
            pass

        @runner.register(2, "second")
        def migrate_v2(conn):
            pass

        runner.run_pending()

        with sqlite_engine.connect() as conn:
            versions = runner._get_applied_versions(conn)

        assert versions == {1, 2}


class TestMigrationResult:
    """Tests for MigrationResult dataclass."""

    def test_successful_result(self):
        result = MigrationResult(version=1, name="test", success=True, duration_ms=42)
        assert result.version == 1
        assert result.name == "test"
        assert result.success is True
        assert result.duration_ms == 42
        assert result.error is None

    def test_failed_result(self):
        result = MigrationResult(
            version=2, name="bad", success=False, duration_ms=10, error="boom"
        )
        assert result.success is False
        assert result.error == "boom"
