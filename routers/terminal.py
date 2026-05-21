"""Terminal router: endpoints for command execution, logs, and policy management.

Exposes:
- POST /api/terminal/run: execute command with confirmation flow
- GET /api/terminal/logs: get command execution history
- GET /api/terminal/policy (admin): get current terminal policy
- PATCH /api/terminal/policy (admin): update allowlist/denylist/folders

Requirements: 9.8
"""

from __future__ import annotations

import os
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, select

from core.audit import ACTION_TERMINAL_BLOCKED, ACTION_TERMINAL_EXECUTE, AuditLogger
from core.deps import UserContext, require_admin_user, require_authenticated_user
from database import engine as db_engine, terminal_command_logs
from services.terminal_service import (
    CommandBlockedError,
    CommandResult,
    TerminalConfig,
    TerminalConfirmationRequired,
    TerminalDisabledError,
    TerminalService,
)

router = APIRouter(tags=["terminal"])


# ── Request / Response models ─────────────────────────────────────────────────


class TerminalRunRequest(BaseModel):
    """Request body for POST /api/terminal/run."""

    command: str = Field(..., min_length=1, max_length=5000)
    working_directory: Optional[str] = None
    timeout: Optional[int] = Field(default=None, ge=1, le=300)
    session_id: Optional[str] = None
    confirmed: bool = False


class TerminalRunResponse(BaseModel):
    """Response for POST /api/terminal/run."""

    status: str  # "executed", "blocked", "confirmation_required", "error"
    command: str
    exit_code: Optional[int] = None
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    execution_ms: Optional[int] = None
    truncated: bool = False
    timed_out: bool = False
    blocked: bool = False
    block_reason: Optional[str] = None
    confirmation_required: bool = False


class TerminalLogEntry(BaseModel):
    """A single terminal command log entry."""

    id: int
    command: str
    working_directory: Optional[str] = None
    exit_code: Optional[int] = None
    output_summary: Optional[str] = None
    execution_ms: Optional[int] = None
    blocked: bool = False
    created_at: Optional[str] = None


class TerminalLogsResponse(BaseModel):
    """Response for GET /api/terminal/logs."""

    logs: List[TerminalLogEntry]
    total: int


class TerminalPolicyResponse(BaseModel):
    """Response for GET /api/terminal/policy."""

    enabled: bool
    require_confirmation: bool
    allowed_folders: List[str]
    command_allowlist: List[str]
    command_denylist: List[str]
    timeout: int
    max_output: int


class TerminalPolicyUpdateRequest(BaseModel):
    """Request body for PATCH /api/terminal/policy."""

    enabled: Optional[bool] = None
    require_confirmation: Optional[bool] = None
    allowed_folders: Optional[List[str]] = None
    command_allowlist: Optional[List[str]] = Field(default=None, max_length=500)
    command_denylist: Optional[List[str]] = Field(default=None, max_length=500)
    timeout: Optional[int] = Field(default=None, ge=1, le=300)
    max_output: Optional[int] = Field(default=None, ge=100, le=1000000)


# ── Service singletons ────────────────────────────────────────────────────────

_terminal_service: Optional[TerminalService] = None


def _get_terminal_service() -> TerminalService:
    """Lazy-init TerminalService with environment-based configuration."""
    global _terminal_service
    if _terminal_service is None:
        config = TerminalConfig(
            enabled=os.getenv("TERMINAL_TOOLS_ENABLED", "false").lower() in ("true", "1", "yes"),
            require_confirmation=os.getenv("TERMINAL_REQUIRE_CONFIRMATION", "true").lower()
            in ("true", "1", "yes"),
            allowed_folders=_parse_list_env("TERMINAL_ALLOWED_FOLDERS"),
            command_allowlist=_parse_list_env("TERMINAL_COMMAND_ALLOWLIST"),
            command_denylist=_parse_list_env("TERMINAL_COMMAND_DENYLIST"),
            timeout=int(os.getenv("TERMINAL_TIMEOUT", "30")),
            max_output=int(os.getenv("TERMINAL_MAX_OUTPUT", "10000")),
        )
        audit = AuditLogger(engine=db_engine)
        _terminal_service = TerminalService(config=config, audit_logger=audit)
    return _terminal_service


def _get_audit_logger() -> AuditLogger:
    """Lazy-init AuditLogger singleton."""
    return AuditLogger(engine=db_engine)


def _parse_list_env(var_name: str) -> List[str]:
    """Parse a comma-separated environment variable into a list of strings."""
    raw = os.getenv(var_name, "").strip()
    if not raw:
        return []
    return [entry.strip() for entry in raw.split(",") if entry.strip()]


# ── POST /api/terminal/run ────────────────────────────────────────────────────


@router.post("/api/terminal/run", response_model=TerminalRunResponse)
def terminal_run(
    request: TerminalRunRequest,
    current_user: UserContext = Depends(require_authenticated_user),
) -> TerminalRunResponse:
    """Execute a terminal command with confirmation flow.

    - Checks if terminal tools are enabled
    - Validates command against security policy
    - Requires per-session confirmation if configured
    - Returns execution result or blocked/error status
    """
    service = _get_terminal_service()

    # Check if terminal is enabled
    try:
        service.check_enabled()
    except TerminalDisabledError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Terminal tools are disabled. An administrator must enable them.",
        )

    # Handle per-session confirmation flow
    session_id = request.session_id or f"api_{current_user.username}"

    if service._config.require_confirmation and not request.confirmed:
        if not service.is_session_confirmed(session_id):
            return TerminalRunResponse(
                status="confirmation_required",
                command=request.command,
                confirmation_required=True,
            )

    # If confirmed flag is set, record the session confirmation
    if request.confirmed:
        service.confirm_session(session_id)

    # Execute the command
    try:
        result: CommandResult = service.execute(
            command=request.command,
            working_directory=request.working_directory,
            session_id=session_id,
            username=current_user.username,
            timeout=request.timeout,
        )
    except TerminalConfirmationRequired:
        return TerminalRunResponse(
            status="confirmation_required",
            command=request.command,
            confirmation_required=True,
        )
    except CommandBlockedError as exc:
        # Log the blocked command to the terminal_command_logs table
        _persist_log(
            username=current_user.username,
            command=request.command,
            working_directory=request.working_directory,
            exit_code=None,
            output_summary=exc.reason,
            execution_ms=0,
            blocked=True,
        )
        return TerminalRunResponse(
            status="blocked",
            command=request.command,
            blocked=True,
            block_reason=exc.reason,
        )

    # Persist the execution log
    output_summary = result.stdout
    if result.stderr:
        output_summary += "\n--- stderr ---\n" + result.stderr
    if len(output_summary) > service.max_output:
        output_summary = output_summary[: service.max_output]

    _persist_log(
        username=current_user.username,
        command=result.command,
        working_directory=request.working_directory,
        exit_code=result.exit_code,
        output_summary=output_summary,
        execution_ms=result.execution_ms,
        blocked=False,
    )

    return TerminalRunResponse(
        status="executed",
        command=result.command,
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        execution_ms=result.execution_ms,
        truncated=result.truncated,
        timed_out=result.timed_out,
    )


# ── GET /api/terminal/logs ────────────────────────────────────────────────────


@router.get("/api/terminal/logs", response_model=TerminalLogsResponse)
def terminal_logs(
    limit: int = 50,
    offset: int = 0,
    current_user: UserContext = Depends(require_authenticated_user),
) -> TerminalLogsResponse:
    """Get command execution history for the current user.

    Returns the most recent command logs, ordered by creation time descending.
    """
    if db_engine is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not available",
        )

    # Clamp limit
    limit = max(1, min(200, limit))
    offset = max(0, offset)

    with db_engine.connect() as conn:
        # Count total for the user
        count_query = select(terminal_command_logs.c.id).where(
            terminal_command_logs.c.username == current_user.username
        )
        total = len(conn.execute(count_query).fetchall())

        # Fetch logs
        query = (
            select(terminal_command_logs)
            .where(terminal_command_logs.c.username == current_user.username)
            .order_by(desc(terminal_command_logs.c.created_at))
            .limit(limit)
            .offset(offset)
        )
        rows = conn.execute(query).fetchall()

    logs = [
        TerminalLogEntry(
            id=row.id,
            command=row.command,
            working_directory=row.working_directory,
            exit_code=row.exit_code,
            output_summary=row.output_summary,
            execution_ms=row.execution_ms,
            blocked=row.blocked or False,
            created_at=row.created_at.isoformat() if row.created_at else None,
        )
        for row in rows
    ]

    return TerminalLogsResponse(logs=logs, total=total)


# ── GET /api/terminal/policy (admin) ──────────────────────────────────────────


@router.get("/api/terminal/policy", response_model=TerminalPolicyResponse)
def get_terminal_policy(
    current_user: UserContext = Depends(require_admin_user),
) -> TerminalPolicyResponse:
    """Get the current terminal security policy (admin only)."""
    service = _get_terminal_service()
    return TerminalPolicyResponse(
        enabled=service._config.enabled,
        require_confirmation=service._config.require_confirmation,
        allowed_folders=service._config.allowed_folders,
        command_allowlist=service._config.command_allowlist,
        command_denylist=service._config.command_denylist,
        timeout=service._config.timeout,
        max_output=service._config.max_output,
    )


# ── PATCH /api/terminal/policy (admin) ────────────────────────────────────────


@router.patch("/api/terminal/policy", response_model=TerminalPolicyResponse)
def update_terminal_policy(
    request: TerminalPolicyUpdateRequest,
    current_user: UserContext = Depends(require_admin_user),
) -> TerminalPolicyResponse:
    """Update the terminal security policy (admin only).

    Allows updating allowlist, denylist, allowed folders, and other settings.
    Changes take effect immediately for subsequent commands.
    """
    global _terminal_service
    service = _get_terminal_service()
    audit = _get_audit_logger()

    # Apply updates to the config
    config = service._config
    changes = {}

    if request.enabled is not None:
        changes["enabled"] = request.enabled
        config.enabled = request.enabled

    if request.require_confirmation is not None:
        changes["require_confirmation"] = request.require_confirmation
        config.require_confirmation = request.require_confirmation

    if request.allowed_folders is not None:
        changes["allowed_folders"] = request.allowed_folders
        config.allowed_folders = request.allowed_folders
        service._policy.set_allowed_folders(request.allowed_folders)

    if request.command_allowlist is not None:
        changes["command_allowlist"] = request.command_allowlist
        config.command_allowlist = request.command_allowlist
        service._policy.set_allowlist(request.command_allowlist)

    if request.command_denylist is not None:
        changes["command_denylist"] = request.command_denylist
        config.command_denylist = request.command_denylist
        service._policy.set_denylist(request.command_denylist)

    if request.timeout is not None:
        changes["timeout"] = request.timeout
        config.timeout = request.timeout

    if request.max_output is not None:
        changes["max_output"] = request.max_output
        config.max_output = request.max_output

    # Log the policy change to audit
    if changes:
        audit.log(
            username=current_user.username,
            action_type="config_change",
            details={"target": "terminal_policy", "changes": changes},
            category="admin",
        )

    return TerminalPolicyResponse(
        enabled=config.enabled,
        require_confirmation=config.require_confirmation,
        allowed_folders=config.allowed_folders,
        command_allowlist=config.command_allowlist,
        command_denylist=config.command_denylist,
        timeout=config.timeout,
        max_output=config.max_output,
    )


# ── Helpers ───────────────────────────────────────────────────────────────────


def _persist_log(
    username: str,
    command: str,
    working_directory: Optional[str],
    exit_code: Optional[int],
    output_summary: Optional[str],
    execution_ms: int,
    blocked: bool,
) -> None:
    """Persist a command execution log entry to the database."""
    if db_engine is None:
        return

    try:
        with db_engine.connect() as conn:
            conn.execute(
                terminal_command_logs.insert().values(
                    username=username,
                    command=command,
                    working_directory=working_directory,
                    exit_code=exit_code,
                    output_summary=output_summary,
                    execution_ms=execution_ms,
                    blocked=blocked,
                )
            )
            conn.commit()
    except Exception:
        # If logging fails, don't block the operation
        pass
