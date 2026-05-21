"""Safe additive-only database migration runner.

Design principles:
- Additive-only migrations (CREATE TABLE IF NOT EXISTS, ADD COLUMN IF NOT EXISTS)
- No DROP TABLE, no DROP COLUMN, no ALTER TYPE
- Each migration is a numbered Python function
- Retry connection up to 3 times with 2s delay
- 30-second timeout for all pending migrations combined
- Rollback on failure: roll back changes from failed step, log error, leave existing data unmodified

Requirements: 3.1, 3.2, 3.5, 3.6, 3.7
"""

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, List, Optional, Set

from sqlalchemy import text
from sqlalchemy.engine import Engine

from logging_utils import get_logger

logger = get_logger(__name__)


class MigrationTimeoutError(Exception):
    """Raised when migrations exceed the allowed timeout."""
    pass


class MigrationConnectionError(Exception):
    """Raised when the database is unreachable after all retry attempts."""
    pass


class MigrationError(Exception):
    """Raised when a migration step fails."""
    pass


@dataclass
class MigrationResult:
    """Result of a single migration execution."""
    version: int
    name: str
    success: bool
    duration_ms: int = 0
    error: Optional[str] = None


class MigrationRunner:
    """Safe additive-only migration runner.

    Executes registered migrations in version order, tracking applied versions
    in a _migrations table. Uses CREATE TABLE IF NOT EXISTS and
    ADD COLUMN IF NOT EXISTS patterns only.
    """

    MIGRATIONS_TABLE = "_migrations"
    DEFAULT_TIMEOUT = 30  # seconds
    MAX_RETRIES = 3
    RETRY_DELAY = 2  # seconds

    def __init__(self, engine: Engine):
        self.engine = engine
        self._migrations: List[tuple] = []  # List of (version, name, callable)

    def register(self, version: int, name: str):
        """Decorator to register a migration function.

        Usage:
            runner = MigrationRunner(engine)

            @runner.register(1, "create_users_table")
            def migrate_v1(conn):
                conn.execute(text("CREATE TABLE IF NOT EXISTS ..."))
        """
        def decorator(func: Callable):
            self._migrations.append((version, name, func))
            # Keep migrations sorted by version
            self._migrations.sort(key=lambda m: m[0])
            return func
        return decorator

    def run_pending(self, timeout_seconds: int = DEFAULT_TIMEOUT) -> List[MigrationResult]:
        """Execute all pending migrations within timeout.

        Args:
            timeout_seconds: Maximum time allowed for all pending migrations (default 30s).

        Returns:
            List of MigrationResult for each executed migration.

        Raises:
            MigrationTimeoutError: If migrations exceed the timeout.
            MigrationConnectionError: If database is unreachable after retries.
        """
        results: List[MigrationResult] = []
        start_time = time.monotonic()
        deadline = start_time + timeout_seconds

        # Ensure connection with retry logic
        conn = self._connect_with_retry()

        try:
            # Ensure _migrations tracking table exists
            self._ensure_migrations_table(conn)

            # Get already-applied versions
            applied = self._get_applied_versions(conn)

            # Filter to pending migrations
            pending = [(v, n, fn) for v, n, fn in self._migrations if v not in applied]

            if not pending:
                logger.info("No pending migrations to run")
                conn.commit()
                return results

            logger.info(f"Running {len(pending)} pending migration(s)")

            for version, name, func in pending:
                # Check timeout before each migration
                elapsed = time.monotonic() - start_time
                if elapsed >= timeout_seconds:
                    error_msg = (
                        f"Migration timeout: exceeded {timeout_seconds}s limit "
                        f"after completing {len(results)} migration(s)"
                    )
                    logger.error(error_msg)
                    conn.rollback()
                    raise MigrationTimeoutError(error_msg)

                migration_start = time.monotonic()
                try:
                    logger.info(f"Running migration v{version}: {name}")
                    func(conn)

                    # Check timeout after migration execution
                    elapsed = time.monotonic() - start_time
                    if elapsed >= timeout_seconds:
                        error_msg = (
                            f"Migration timeout: exceeded {timeout_seconds}s limit "
                            f"after completing {len(results)} migration(s)"
                        )
                        logger.error(error_msg)
                        conn.rollback()
                        raise MigrationTimeoutError(error_msg)

                    self._mark_applied(conn, version, name)
                    conn.commit()

                    duration_ms = int((time.monotonic() - migration_start) * 1000)
                    result = MigrationResult(
                        version=version,
                        name=name,
                        success=True,
                        duration_ms=duration_ms,
                    )
                    results.append(result)
                    logger.info(
                        f"Migration v{version} ({name}) completed in {duration_ms}ms"
                    )

                except MigrationTimeoutError:
                    raise
                except Exception as e:
                    # Rollback changes from this failed migration step
                    conn.rollback()
                    duration_ms = int((time.monotonic() - migration_start) * 1000)
                    error_msg = f"Migration v{version} ({name}) failed: {e}"
                    logger.error(error_msg, exc_info=True)

                    result = MigrationResult(
                        version=version,
                        name=name,
                        success=False,
                        duration_ms=duration_ms,
                        error=str(e),
                    )
                    results.append(result)
                    raise MigrationError(error_msg) from e

        finally:
            conn.close()

        total_ms = int((time.monotonic() - start_time) * 1000)
        logger.info(
            f"All migrations completed in {total_ms}ms "
            f"({len(results)} migration(s) applied)"
        )
        return results

    def _connect_with_retry(self):
        """Establish database connection with retry logic.

        Retries up to 3 times with 2-second delay between attempts.

        Returns:
            A SQLAlchemy connection object.

        Raises:
            MigrationConnectionError: If all retry attempts fail.
        """
        last_error = None
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                conn = self.engine.connect()
                # Verify the connection is alive
                conn.execute(text("SELECT 1"))
                logger.info(f"Database connection established (attempt {attempt})")
                return conn
            except Exception as e:
                last_error = e
                if attempt < self.MAX_RETRIES:
                    logger.warning(
                        f"Database connection attempt {attempt}/{self.MAX_RETRIES} failed: {e}. "
                        f"Retrying in {self.RETRY_DELAY}s..."
                    )
                    time.sleep(self.RETRY_DELAY)
                else:
                    logger.error(
                        f"Database connection failed after {self.MAX_RETRIES} attempts: {e}"
                    )

        raise MigrationConnectionError(
            f"Database unreachable after {self.MAX_RETRIES} attempts "
            f"with {self.RETRY_DELAY}s delay. Last error: {last_error}"
        )

    def _ensure_migrations_table(self, conn) -> None:
        """Create the _migrations tracking table if it doesn't exist."""
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS _migrations (
                version INTEGER PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """))
        conn.commit()

    def _get_applied_versions(self, conn) -> Set[int]:
        """Read applied migration versions from _migrations table."""
        result = conn.execute(text("SELECT version FROM _migrations ORDER BY version"))
        return {row[0] for row in result.fetchall()}

    def _mark_applied(self, conn, version: int, name: str) -> None:
        """Record a successfully applied migration."""
        conn.execute(
            text(
                "INSERT INTO _migrations (version, name, applied_at) "
                "VALUES (:version, :name, :applied_at)"
            ),
            {
                "version": version,
                "name": name,
                "applied_at": datetime.now(timezone.utc),
            },
        )
