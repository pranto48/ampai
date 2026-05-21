"""Terminal Service — shell command executor with security enforcement.

Implements TerminalService with OS-aware shell detection (macOS shell,
Windows PowerShell, Windows CMD), disabled-by-default enforcement,
per-session confirmation, configurable timeout and output limits,
and full audit logging.

Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7, 9.9
"""

from __future__ import annotations

import os
import platform
import subprocess
import time
from dataclasses import dataclass, field
from typing import List, Optional, Set

from logging_utils import get_logger
from policy.terminal_policy import TerminalPolicy, ValidationResult

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Timeout range constraints
MIN_TIMEOUT = 1
MAX_TIMEOUT = 300
DEFAULT_TIMEOUT = 30

# Output limit range constraints
MIN_OUTPUT_LIMIT = 100
MAX_OUTPUT_LIMIT = 1_000_000
DEFAULT_OUTPUT_LIMIT = 10_000


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class TerminalConfig:
    """Configuration for the terminal service."""

    enabled: bool = False
    require_confirmation: bool = True
    allowed_folders: List[str] = field(default_factory=list)
    command_allowlist: List[str] = field(default_factory=list)
    command_denylist: List[str] = field(default_factory=list)
    timeout: int = DEFAULT_TIMEOUT
    max_output: int = DEFAULT_OUTPUT_LIMIT


@dataclass
class CommandResult:
    """Result of a terminal command execution."""

    command: str
    exit_code: int
    stdout: str
    stderr: str
    execution_ms: int
    truncated: bool
    timed_out: bool = False
    blocked: bool = False
    block_reason: Optional[str] = None


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class TerminalDisabledError(Exception):
    """Raised when terminal tools are disabled."""

    pass


class TerminalConfirmationRequired(Exception):
    """Raised when per-session confirmation has not been granted."""

    pass


class CommandBlockedError(Exception):
    """Raised when a command is blocked by security policy."""

    def __init__(self, reason: str, matched_pattern: Optional[str] = None):
        self.reason = reason
        self.matched_pattern = matched_pattern
        super().__init__(reason)


# ---------------------------------------------------------------------------
# Service class
# ---------------------------------------------------------------------------


class TerminalService:
    """Shell command executor with security enforcement.

    Supports macOS shell, Windows PowerShell, and Windows CMD with
    auto-detection. Enforces disabled-by-default, per-session confirmation,
    configurable timeout and output limits, and audit logging.
    """

    def __init__(self, config: TerminalConfig, audit_logger=None):
        """Initialize the terminal service.

        Args:
            config: Terminal configuration settings.
            audit_logger: Optional AuditLogger instance for recording events.
        """
        self._config = config
        self._audit_logger = audit_logger
        self._policy = TerminalPolicy(
            denylist=config.command_denylist,
            allowlist=config.command_allowlist,
            allowed_folders=config.allowed_folders,
        )
        # Track sessions that have confirmed terminal access
        self._confirmed_sessions: Set[str] = set()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def enabled(self) -> bool:
        """Whether terminal tools are enabled."""
        return self._config.enabled

    @property
    def timeout(self) -> int:
        """Configured timeout in seconds (clamped to valid range)."""
        return self._clamp_timeout(self._config.timeout)

    @property
    def max_output(self) -> int:
        """Configured output limit in characters (clamped to valid range)."""
        return self._clamp_output_limit(self._config.max_output)

    def check_enabled(self) -> None:
        """Check if terminal tools are enabled.

        Raises:
            TerminalDisabledError: If terminal tools are disabled.
        """
        if not self._config.enabled:
            raise TerminalDisabledError(
                "Terminal tools are disabled. An administrator must enable "
                "them via the TERMINAL_TOOLS_ENABLED setting."
            )

    def confirm_session(self, session_id: str) -> None:
        """Record that a session has confirmed terminal access.

        Args:
            session_id: The session identifier to confirm.
        """
        self._confirmed_sessions.add(session_id)

    def revoke_session(self, session_id: str) -> None:
        """Revoke terminal confirmation for a session.

        Args:
            session_id: The session identifier to revoke.
        """
        self._confirmed_sessions.discard(session_id)

    def is_session_confirmed(self, session_id: str) -> bool:
        """Check if a session has confirmed terminal access.

        Args:
            session_id: The session identifier to check.

        Returns:
            True if the session has been confirmed.
        """
        if not self._config.require_confirmation:
            return True
        return session_id in self._confirmed_sessions

    def validate_command(
        self, command: str, working_directory: Optional[str] = None
    ) -> ValidationResult:
        """Validate a command against security policy.

        Delegates to TerminalPolicy for dangerous pattern detection,
        denylist/allowlist enforcement, and allowed folder checks.

        Args:
            command: The shell command string to validate.
            working_directory: The directory the command will execute in.

        Returns:
            ValidationResult indicating whether the command is allowed.
        """
        return self._policy.validate_command(command, working_directory)

    def execute(
        self,
        command: str,
        working_directory: Optional[str] = None,
        session_id: Optional[str] = None,
        username: Optional[str] = None,
        timeout: Optional[int] = None,
        max_output: Optional[int] = None,
    ) -> CommandResult:
        """Execute a shell command with security enforcement.

        Performs all checks (enabled, session confirmation, policy validation)
        then executes the command with the configured timeout and output limit.
        Logs the result to the audit logger.

        Args:
            command: The shell command to execute.
            working_directory: Directory to execute in (defaults to cwd).
            session_id: Current session ID for confirmation check.
            username: Username for audit logging.
            timeout: Override timeout in seconds (clamped to valid range).
            max_output: Override output limit in characters (clamped to valid range).

        Returns:
            CommandResult with execution details.

        Raises:
            TerminalDisabledError: If terminal tools are disabled.
            TerminalConfirmationRequired: If session not confirmed.
            CommandBlockedError: If command is blocked by policy.
        """
        # 1. Check enabled
        self.check_enabled()

        # 2. Check per-session confirmation
        if session_id and not self.is_session_confirmed(session_id):
            raise TerminalConfirmationRequired(
                "Terminal access requires per-session confirmation. "
                "Please confirm terminal access for this session."
            )

        # 3. Validate command against policy
        validation = self.validate_command(command, working_directory)
        if not validation.allowed:
            # Log blocked command to audit
            self._log_blocked(command, working_directory, validation, username, session_id)
            raise CommandBlockedError(
                reason=validation.block_reason or "Command blocked by security policy",
                matched_pattern=validation.matched_pattern,
            )

        # 4. Resolve execution parameters
        effective_timeout = self._clamp_timeout(timeout if timeout is not None else self._config.timeout)
        effective_max_output = self._clamp_output_limit(
            max_output if max_output is not None else self._config.max_output
        )
        effective_cwd = working_directory or os.getcwd()
        shell_cmd, shell_flag = self._detect_shell()

        # 5. Execute command
        start_time = time.time()
        timed_out = False
        truncated = False

        try:
            process = subprocess.Popen(
                shell_cmd + [command] if shell_flag else command,
                shell=not shell_flag,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=effective_cwd,
                text=True,
            )

            try:
                stdout, stderr = process.communicate(timeout=effective_timeout)
            except subprocess.TimeoutExpired:
                # Kill the process and capture partial output
                process.kill()
                stdout, stderr = process.communicate()
                timed_out = True

            exit_code = process.returncode

        except OSError as exc:
            # Handle cases where the shell or command cannot be found
            execution_ms = int((time.time() - start_time) * 1000)
            result = CommandResult(
                command=command,
                exit_code=-1,
                stdout="",
                stderr=str(exc),
                execution_ms=execution_ms,
                truncated=False,
                timed_out=False,
                blocked=False,
            )
            self._log_execution(result, effective_cwd, username, session_id)
            return result

        execution_ms = int((time.time() - start_time) * 1000)

        # 6. Enforce output limit
        combined_output_len = len(stdout) + len(stderr)
        if combined_output_len > effective_max_output:
            truncated = True
            # Truncate stdout first, then stderr if needed
            if len(stdout) > effective_max_output:
                stdout = stdout[:effective_max_output]
                stderr = ""
            else:
                remaining = effective_max_output - len(stdout)
                stderr = stderr[:remaining]

        result = CommandResult(
            command=command,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            execution_ms=execution_ms,
            truncated=truncated,
            timed_out=timed_out,
        )

        # 7. Log to audit
        self._log_execution(result, effective_cwd, username, session_id)

        return result

    # ------------------------------------------------------------------
    # Shell detection
    # ------------------------------------------------------------------

    def _detect_shell(self) -> tuple:
        """Detect the appropriate shell for the current OS.

        Returns:
            Tuple of (shell_command_list, use_shell_flag).
            If use_shell_flag is True, the command list is used with Popen;
            otherwise shell=True is used with the command as a string.
        """
        system = platform.system().lower()

        if system == "windows":
            # Prefer PowerShell if available, fall back to CMD
            if self._is_powershell_available():
                return (["powershell", "-NoProfile", "-Command"], True)
            else:
                return (["cmd", "/c"], True)
        else:
            # macOS and Linux: use the default shell
            shell = os.environ.get("SHELL", "/bin/sh")
            return ([shell, "-c"], True)

    @staticmethod
    def _is_powershell_available() -> bool:
        """Check if PowerShell is available on the system."""
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", "echo ok"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            return False

    # ------------------------------------------------------------------
    # Audit logging
    # ------------------------------------------------------------------

    def _log_execution(
        self,
        result: CommandResult,
        working_directory: str,
        username: Optional[str],
        session_id: Optional[str],
    ) -> None:
        """Log a command execution to the audit logger."""
        if self._audit_logger is None:
            return

        # Truncate output for audit log (use configured max_output)
        output_for_audit = result.stdout
        if result.stderr:
            output_for_audit += "\n--- stderr ---\n" + result.stderr
        if len(output_for_audit) > self.max_output:
            output_for_audit = output_for_audit[: self.max_output]

        try:
            from core.audit import ACTION_TERMINAL_EXECUTE

            self._audit_logger.log(
                username=username or "system",
                action_type=ACTION_TERMINAL_EXECUTE,
                details={
                    "command": result.command,
                    "working_directory": working_directory,
                    "exit_code": result.exit_code,
                    "execution_ms": result.execution_ms,
                    "output": output_for_audit,
                    "truncated": result.truncated,
                    "timed_out": result.timed_out,
                },
                session_id=session_id,
            )
        except Exception as exc:
            logger.error(
                "Failed to log terminal execution to audit",
                extra={"error": str(exc)},
                exc_info=exc,
            )

    def _log_blocked(
        self,
        command: str,
        working_directory: Optional[str],
        validation: ValidationResult,
        username: Optional[str],
        session_id: Optional[str],
    ) -> None:
        """Log a blocked command to the audit logger."""
        if self._audit_logger is None:
            return

        try:
            from core.audit import ACTION_TERMINAL_BLOCKED

            self._audit_logger.log(
                username=username or "system",
                action_type=ACTION_TERMINAL_BLOCKED,
                details={
                    "command": command,
                    "working_directory": working_directory,
                    "block_reason": validation.block_reason,
                    "matched_pattern": validation.matched_pattern,
                },
                session_id=session_id,
            )
        except Exception as exc:
            logger.error(
                "Failed to log blocked command to audit",
                extra={"error": str(exc)},
                exc_info=exc,
            )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _clamp_timeout(value: int) -> int:
        """Clamp timeout to valid range [1, 300]."""
        return max(MIN_TIMEOUT, min(MAX_TIMEOUT, value))

    @staticmethod
    def _clamp_output_limit(value: int) -> int:
        """Clamp output limit to valid range [100, 1000000]."""
        return max(MIN_OUTPUT_LIMIT, min(MAX_OUTPUT_LIMIT, value))
