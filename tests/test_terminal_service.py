"""Tests for services/terminal_service.py.

Validates the TerminalService shell command executor:
- Disabled-by-default enforcement (Requirement 9.2)
- Per-session confirmation (Requirement 9.2)
- Command validation delegation to TerminalPolicy (Requirements 9.3, 9.4, 9.5)
- Configurable timeout enforcement (Requirement 9.6, 9.7)
- Configurable output limit (Requirement 9.6)
- OS-aware shell detection (Requirement 9.1)
- Audit logging of executions and blocked commands (Requirement 9.9)
"""

import platform
from unittest.mock import MagicMock, patch

import pytest

import sys
import os
import importlib.util

# Import terminal_service directly to avoid services/__init__.py import chain
# which pulls in heavy dependencies (langchain, database, etc.)
_service_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "services",
    "terminal_service.py",
)
_spec = importlib.util.spec_from_file_location("services.terminal_service", _service_path)
_module = importlib.util.module_from_spec(_spec)
sys.modules["services.terminal_service"] = _module
_spec.loader.exec_module(_module)

CommandBlockedError = _module.CommandBlockedError
CommandResult = _module.CommandResult
TerminalConfig = _module.TerminalConfig
TerminalConfirmationRequired = _module.TerminalConfirmationRequired
TerminalDisabledError = _module.TerminalDisabledError
TerminalService = _module.TerminalService
DEFAULT_TIMEOUT = _module.DEFAULT_TIMEOUT
DEFAULT_OUTPUT_LIMIT = _module.DEFAULT_OUTPUT_LIMIT
MIN_TIMEOUT = _module.MIN_TIMEOUT
MAX_TIMEOUT = _module.MAX_TIMEOUT
MIN_OUTPUT_LIMIT = _module.MIN_OUTPUT_LIMIT
MAX_OUTPUT_LIMIT = _module.MAX_OUTPUT_LIMIT


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def default_config():
    """A disabled-by-default terminal config."""
    return TerminalConfig(enabled=False)


@pytest.fixture
def enabled_config():
    """An enabled terminal config with no confirmation required."""
    return TerminalConfig(enabled=True, require_confirmation=False)


@pytest.fixture
def enabled_with_confirmation():
    """An enabled terminal config requiring per-session confirmation."""
    return TerminalConfig(enabled=True, require_confirmation=True)


@pytest.fixture
def mock_audit_logger():
    """A mock AuditLogger."""
    return MagicMock()


# ---------------------------------------------------------------------------
# Test: Disabled by default (Requirement 9.2)
# ---------------------------------------------------------------------------


class TestCheckEnabled:
    """Terminal tools are disabled by default."""

    def test_disabled_raises_error(self, default_config):
        service = TerminalService(default_config)
        with pytest.raises(TerminalDisabledError):
            service.check_enabled()

    def test_enabled_does_not_raise(self, enabled_config):
        service = TerminalService(enabled_config)
        service.check_enabled()  # Should not raise

    def test_execute_when_disabled_raises(self, default_config):
        service = TerminalService(default_config)
        with pytest.raises(TerminalDisabledError):
            service.execute("echo hello")


# ---------------------------------------------------------------------------
# Test: Per-session confirmation (Requirement 9.2)
# ---------------------------------------------------------------------------


class TestSessionConfirmation:
    """Per-session confirmation enforcement."""

    def test_unconfirmed_session_raises(self, enabled_with_confirmation):
        service = TerminalService(enabled_with_confirmation)
        with pytest.raises(TerminalConfirmationRequired):
            service.execute("echo hello", session_id="session-1")

    def test_confirmed_session_allows_execution(self, enabled_with_confirmation):
        service = TerminalService(enabled_with_confirmation)
        service.confirm_session("session-1")
        result = service.execute("echo hello", session_id="session-1")
        assert result.exit_code == 0

    def test_revoke_session_blocks_again(self, enabled_with_confirmation):
        service = TerminalService(enabled_with_confirmation)
        service.confirm_session("session-1")
        service.revoke_session("session-1")
        with pytest.raises(TerminalConfirmationRequired):
            service.execute("echo hello", session_id="session-1")

    def test_no_confirmation_required_allows_all(self, enabled_config):
        service = TerminalService(enabled_config)
        assert service.is_session_confirmed("any-session") is True

    def test_is_session_confirmed_false_by_default(self, enabled_with_confirmation):
        service = TerminalService(enabled_with_confirmation)
        assert service.is_session_confirmed("unknown") is False


# ---------------------------------------------------------------------------
# Test: Command validation (Requirements 9.3, 9.4, 9.5)
# ---------------------------------------------------------------------------


class TestValidateCommand:
    """Command validation delegates to TerminalPolicy."""

    def test_dangerous_command_blocked(self, enabled_config):
        service = TerminalService(enabled_config)
        result = service.validate_command("rm -rf /")
        assert result.blocked is True

    def test_safe_command_allowed(self, enabled_config):
        service = TerminalService(enabled_config)
        result = service.validate_command("echo hello")
        assert result.allowed is True

    def test_denylist_blocks_command(self):
        config = TerminalConfig(enabled=True, require_confirmation=False, command_denylist=["curl"])
        service = TerminalService(config)
        result = service.validate_command("curl http://evil.com")
        assert result.blocked is True

    def test_execute_blocked_command_raises(self, enabled_config, mock_audit_logger):
        service = TerminalService(enabled_config, audit_logger=mock_audit_logger)
        with pytest.raises(CommandBlockedError) as exc_info:
            service.execute("rm -rf /")
        assert "dangerous pattern" in exc_info.value.reason


# ---------------------------------------------------------------------------
# Test: Command execution (Requirements 9.1, 9.6, 9.7)
# ---------------------------------------------------------------------------


class TestExecute:
    """Command execution with timeout and output limits."""

    def test_simple_echo(self, enabled_config):
        service = TerminalService(enabled_config)
        result = service.execute("echo hello")
        assert result.exit_code == 0
        assert "hello" in result.stdout
        assert result.timed_out is False
        assert result.blocked is False

    def test_command_with_nonzero_exit(self, enabled_config):
        service = TerminalService(enabled_config)
        # Use a command that will fail
        result = service.execute("ls /nonexistent_path_xyz_12345")
        assert result.exit_code != 0

    def test_timeout_terminates_command(self):
        config = TerminalConfig(enabled=True, require_confirmation=False, timeout=1)
        service = TerminalService(config)
        # sleep 10 should be killed after 1 second
        result = service.execute("sleep 10", timeout=1)
        assert result.timed_out is True
        assert result.execution_ms >= 900  # At least ~1 second

    def test_output_truncation(self):
        config = TerminalConfig(enabled=True, require_confirmation=False, max_output=100)
        service = TerminalService(config)
        # Generate output longer than 100 chars using a repeated string
        result = service.execute("python3 -c \"print('x' * 200)\"")
        assert result.truncated is True
        assert len(result.stdout) + len(result.stderr) <= 100

    def test_execution_ms_recorded(self, enabled_config):
        service = TerminalService(enabled_config)
        result = service.execute("echo fast")
        assert result.execution_ms >= 0

    def test_working_directory_respected(self, enabled_config, tmp_path):
        service = TerminalService(enabled_config)
        result = service.execute("pwd", working_directory=str(tmp_path))
        assert str(tmp_path) in result.stdout


# ---------------------------------------------------------------------------
# Test: Timeout and output limit clamping (Requirement 9.6)
# ---------------------------------------------------------------------------


class TestConfigClamping:
    """Timeout and output limits are clamped to valid ranges."""

    def test_timeout_below_min_clamped(self):
        config = TerminalConfig(enabled=True, timeout=0)
        service = TerminalService(config)
        assert service.timeout == MIN_TIMEOUT

    def test_timeout_above_max_clamped(self):
        config = TerminalConfig(enabled=True, timeout=999)
        service = TerminalService(config)
        assert service.timeout == MAX_TIMEOUT

    def test_timeout_within_range_unchanged(self):
        config = TerminalConfig(enabled=True, timeout=60)
        service = TerminalService(config)
        assert service.timeout == 60

    def test_output_limit_below_min_clamped(self):
        config = TerminalConfig(enabled=True, max_output=10)
        service = TerminalService(config)
        assert service.max_output == MIN_OUTPUT_LIMIT

    def test_output_limit_above_max_clamped(self):
        config = TerminalConfig(enabled=True, max_output=9_999_999)
        service = TerminalService(config)
        assert service.max_output == MAX_OUTPUT_LIMIT

    def test_output_limit_within_range_unchanged(self):
        config = TerminalConfig(enabled=True, max_output=5000)
        service = TerminalService(config)
        assert service.max_output == 5000

    def test_default_timeout(self):
        config = TerminalConfig(enabled=True)
        service = TerminalService(config)
        assert service.timeout == DEFAULT_TIMEOUT

    def test_default_output_limit(self):
        config = TerminalConfig(enabled=True)
        service = TerminalService(config)
        assert service.max_output == DEFAULT_OUTPUT_LIMIT


# ---------------------------------------------------------------------------
# Test: Shell detection (Requirement 9.1)
# ---------------------------------------------------------------------------


class TestShellDetection:
    """OS-aware shell detection."""

    def test_detect_shell_returns_tuple(self, enabled_config):
        service = TerminalService(enabled_config)
        shell_cmd, shell_flag = service._detect_shell()
        assert isinstance(shell_cmd, list)
        assert isinstance(shell_flag, bool)

    @patch("platform.system", return_value="Darwin")
    def test_macos_uses_shell(self, mock_system, enabled_config):
        service = TerminalService(enabled_config)
        shell_cmd, shell_flag = service._detect_shell()
        assert shell_flag is True
        # Should use SHELL env var or /bin/sh
        assert shell_cmd[0].endswith("sh") or shell_cmd[0].endswith("zsh") or shell_cmd[0].endswith("bash")

    @patch("platform.system", return_value="Linux")
    def test_linux_uses_shell(self, mock_system, enabled_config):
        service = TerminalService(enabled_config)
        shell_cmd, shell_flag = service._detect_shell()
        assert shell_flag is True

    @patch("platform.system", return_value="Windows")
    @patch.object(TerminalService, "_is_powershell_available", return_value=True)
    def test_windows_prefers_powershell(self, mock_ps, mock_system, enabled_config):
        service = TerminalService(enabled_config)
        shell_cmd, shell_flag = service._detect_shell()
        assert "powershell" in shell_cmd[0].lower()
        assert shell_flag is True

    @patch("platform.system", return_value="Windows")
    @patch.object(TerminalService, "_is_powershell_available", return_value=False)
    def test_windows_falls_back_to_cmd(self, mock_ps, mock_system, enabled_config):
        service = TerminalService(enabled_config)
        shell_cmd, shell_flag = service._detect_shell()
        assert "cmd" in shell_cmd[0].lower()
        assert shell_flag is True


# ---------------------------------------------------------------------------
# Test: Audit logging (Requirement 9.9)
# ---------------------------------------------------------------------------


class TestAuditLogging:
    """Audit logging of executions and blocked commands."""

    def test_execution_logged(self, enabled_config, mock_audit_logger):
        service = TerminalService(enabled_config, audit_logger=mock_audit_logger)
        service.execute("echo audit_test", username="testuser", session_id="sess-1")
        mock_audit_logger.log.assert_called_once()
        call_kwargs = mock_audit_logger.log.call_args[1]
        assert call_kwargs["username"] == "testuser"
        assert call_kwargs["action_type"] == "terminal_execute"
        assert call_kwargs["session_id"] == "sess-1"
        details = call_kwargs["details"]
        assert details["command"] == "echo audit_test"
        assert "exit_code" in details
        assert "execution_ms" in details
        assert "output" in details
        assert "working_directory" in details

    def test_blocked_command_logged(self, enabled_config, mock_audit_logger):
        service = TerminalService(enabled_config, audit_logger=mock_audit_logger)
        with pytest.raises(CommandBlockedError):
            service.execute("rm -rf /", username="testuser", session_id="sess-1")
        mock_audit_logger.log.assert_called_once()
        call_kwargs = mock_audit_logger.log.call_args[1]
        assert call_kwargs["action_type"] == "terminal_blocked"
        assert call_kwargs["details"]["command"] == "rm -rf /"

    def test_no_audit_logger_does_not_crash(self, enabled_config):
        service = TerminalService(enabled_config, audit_logger=None)
        result = service.execute("echo no_audit")
        assert result.exit_code == 0

    def test_audit_logger_failure_does_not_crash(self, enabled_config):
        broken_logger = MagicMock()
        broken_logger.log.side_effect = Exception("DB connection failed")
        service = TerminalService(enabled_config, audit_logger=broken_logger)
        # Should not raise even though audit logging fails
        result = service.execute("echo resilient")
        assert result.exit_code == 0
