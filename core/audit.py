"""
Audit Logger — append-only audit event recording for security-sensitive actions.

Provides the AuditLogger class that writes to the audit_events table and supports
filtered queries. If logging fails, the original operation continues uninterrupted
and the failure is logged to the application error log.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from logging_utils import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Action type constants
# ---------------------------------------------------------------------------

ACTION_MEMORY_WRITE = "memory_write"
ACTION_MEMORY_READ = "memory_read"
ACTION_MEMORY_DELETE = "memory_delete"
ACTION_BROWSER_ACTION = "browser_action"
ACTION_BROWSER_NAVIGATE = "browser_navigate"
ACTION_TERMINAL_EXECUTE = "terminal_execute"
ACTION_TERMINAL_BLOCKED = "terminal_blocked"
ACTION_TELEGRAM_MESSAGE = "telegram_message"
ACTION_BACKUP_RUN = "backup_run"
ACTION_BACKUP_RESTORE = "backup_restore"
ACTION_LOGIN_ATTEMPT = "login_attempt"
ACTION_WEB_SEARCH = "web_search"
ACTION_CONFIG_CHANGE = "config_change"

ALL_ACTION_TYPES = (
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
)

# Maximum character length for the details field (serialized JSON).
MAX_DETAILS_CHARS = 2000

# Query limits
MAX_QUERY_LIMIT = 1000
DEFAULT_QUERY_LIMIT = 100


class AuditLogger:
    """Append-only audit event logger backed by the audit_events table."""

    def __init__(self, engine):
        self.engine = engine

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def log(
        self,
        username: str,
        action_type: str,
        details: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None,
        category: Optional[str] = None,
    ) -> None:
        """
        Append an audit event to the audit_events table.

        If the insert fails for any reason, the failure is logged to the
        application error log and the caller is NOT interrupted.
        """
        try:
            # Serialize and truncate details to MAX_DETAILS_CHARS
            details_json: Optional[str] = None
            if details is not None:
                serialized = json.dumps(details, default=str)
                if len(serialized) > MAX_DETAILS_CHARS:
                    serialized = serialized[:MAX_DETAILS_CHARS]
                details_json = serialized

            with self.engine.begin() as conn:
                conn.execute(
                    text(
                        "INSERT INTO audit_events "
                        "(username, action_type, session_id, category, details, created_at) "
                        "VALUES (:username, :action_type, :session_id, :category, "
                        "CAST(:details AS jsonb), NOW())"
                    ),
                    {
                        "username": username,
                        "action_type": action_type,
                        "session_id": session_id,
                        "category": category,
                        "details": details_json,
                    },
                )
        except Exception as exc:
            # Requirement 15.7: If audit logging fails, continue original
            # operation and log failure to application error log.
            logger.error(
                "Failed to write audit event",
                extra={
                    "audit_username": username,
                    "audit_action_type": action_type,
                    "audit_session_id": session_id,
                    "error": str(exc),
                },
                exc_info=exc,
            )

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def query(
        self,
        action_type: Optional[str] = None,
        username: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        session_id: Optional[str] = None,
        limit: int = DEFAULT_QUERY_LIMIT,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Query audit events with optional filters.

        Parameters
        ----------
        action_type : filter by action type
        username : filter by username
        date_from : inclusive lower bound on created_at
        date_to : inclusive upper bound on created_at
        session_id : filter by session_id
        limit : max rows to return (capped at MAX_QUERY_LIMIT)
        offset : pagination offset

        Returns
        -------
        List of audit event dicts ordered by created_at DESC.
        """
        # Enforce limit cap
        if limit < 1:
            limit = DEFAULT_QUERY_LIMIT
        if limit > MAX_QUERY_LIMIT:
            limit = MAX_QUERY_LIMIT

        if offset < 0:
            offset = 0

        conditions: List[str] = []
        params: Dict[str, Any] = {}

        if action_type is not None:
            conditions.append("action_type = :action_type")
            params["action_type"] = action_type

        if username is not None:
            conditions.append("username = :username")
            params["username"] = username

        if date_from is not None:
            conditions.append("created_at >= :date_from")
            params["date_from"] = date_from

        if date_to is not None:
            conditions.append("created_at <= :date_to")
            params["date_to"] = date_to

        if session_id is not None:
            conditions.append("session_id = :session_id")
            params["session_id"] = session_id

        where_clause = ""
        if conditions:
            where_clause = "WHERE " + " AND ".join(conditions)

        sql = (
            f"SELECT id, username, action_type, session_id, category, details, created_at "
            f"FROM audit_events {where_clause} "
            f"ORDER BY created_at DESC "
            f"LIMIT :limit OFFSET :offset"
        )
        params["limit"] = limit
        params["offset"] = offset

        try:
            with self.engine.connect() as conn:
                rows = conn.execute(text(sql), params).mappings().all()
                return [
                    {
                        "id": row["id"],
                        "username": row["username"],
                        "action_type": row["action_type"],
                        "session_id": row["session_id"],
                        "category": row["category"],
                        "details": row["details"],
                        "created_at": (
                            row["created_at"].isoformat()
                            if isinstance(row["created_at"], datetime)
                            else str(row["created_at"])
                        ),
                    }
                    for row in rows
                ]
        except Exception as exc:
            logger.error(
                "Failed to query audit events",
                extra={"error": str(exc)},
                exc_info=exc,
            )
            return []
