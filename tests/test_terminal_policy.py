"""Tests for policy/terminal_policy.py.

Validates command security validation for terminal access.
- Dangerous patterns are always blocked (Requirement 9.4)
- Denylist takes precedence over allowlist (Requirement 9.4, 9.5)
- Commands referencing paths outside allowed folders are rejected (Requirement 9.3)
"""

import pytest

from policy.terminal_policy import TerminalPolicy, ValidationResult, DANGEROUS_PATTERNS, MAX_LIST_ENTRIES


class TestDangerousPatterns:
    """Dangerous command patterns are always blocked (Requirement 9.4)."""

    def test_rm_rf_root_blocked(self):
        policy = TerminalPolicy()
        result = policy.validate_command("rm -rf /")
        assert result.blocked is True
        assert result.allowed is False
        assert "dangerous pattern" in result.block_reason

    def test_rm_r_root_blocked(self):
        policy = TerminalPolicy()
        result = policy.validate_command("rm -r /home")
        assert result.blocked is True

    def test_rm_recursive_flag_blocked(self):
        policy = TerminalPolicy()
        result = policy.validate_command("rm --recursive /var")
        assert result.blocked is True

    def test_format_command_blocked(self):
        policy = TerminalPolicy()
        result = policy.validate_command("format C:")
        assert result.blocked is True

    def test_del_s_blocked(self):
        policy = TerminalPolicy()
        result = policy.validate_command("del /S C:\\Windows")
        assert result.blocked is True

    def test_remove_item_recurse_system_blocked(self):
        policy = TerminalPolicy()
        result = policy.validate_command("Remove-Item -Recurse C:\\Windows\\System32")
        assert result.blocked is True

    def test_shutdown_blocked(self):
        policy = TerminalPolicy()
        result = policy.validate_command("shutdown -h now")
        assert result.blocked is True

    def test_regedit_blocked(self):
        policy = TerminalPolicy()
        result = policy.validate_command("regedit /s malicious.reg")
        assert result.blocked is True

    def test_reg_add_blocked(self):
        policy = TerminalPolicy()
        result = policy.validate_command("reg add HKLM\\Software\\Test")
        assert result.blocked is True

    def test_reg_delete_blocked(self):
        policy = TerminalPolicy()
        result = policy.validate_command("reg delete HKLM\\Software\\Test")
        assert result.blocked is True

    def test_mimikatz_blocked(self):
        policy = TerminalPolicy()
        result = policy.validate_command("./mimikatz.exe")
        assert result.blocked is True

    def test_credential_dump_blocked(self):
        policy = TerminalPolicy()
        result = policy.validate_command("credential.dump --all")
        assert result.blocked is True

    def test_token_dump_blocked(self):
        policy = TerminalPolicy()
        result = policy.validate_command("token.dump session")
        assert result.blocked is True

    def test_browser_password_export_blocked(self):
        policy = TerminalPolicy()
        result = policy.validate_command("browser password export --chrome")
        assert result.blocked is True

    def test_chrome_login_data_blocked(self):
        policy = TerminalPolicy()
        result = policy.validate_command("cp chrome login data /tmp/stolen")
        assert result.blocked is True

    def test_keylogger_blocked(self):
        policy = TerminalPolicy()
        result = policy.validate_command("start keylogger")
        assert result.blocked is True

    def test_key_logger_variant_blocked(self):
        policy = TerminalPolicy()
        result = policy.validate_command("install key_logger")
        assert result.blocked is True

    def test_stealth_blocked(self):
        policy = TerminalPolicy()
        result = policy.validate_command("run stealth mode")
        assert result.blocked is True

    def test_hidden_monitor_blocked(self):
        policy = TerminalPolicy()
        result = policy.validate_command("hidden monitor start")
        assert result.blocked is True

    def test_safe_command_allowed(self):
        policy = TerminalPolicy()
        result = policy.validate_command("ls -la")
        assert result.allowed is True
        assert result.blocked is False

    def test_safe_git_command_allowed(self):
        policy = TerminalPolicy()
        result = policy.validate_command("git status")
        assert result.allowed is True

    def test_case_insensitive_dangerous_pattern(self):
        policy = TerminalPolicy()
        result = policy.validate_command("SHUTDOWN -h now")
        assert result.blocked is True

    def test_dangerous_pattern_even_with_allowlist(self):
        """Dangerous patterns block even if command is in allowlist."""
        policy = TerminalPolicy(allowlist=["rm -rf /"])
        result = policy.validate_command("rm -rf /")
        assert result.blocked is True
        assert "dangerous pattern" in result.block_reason


class TestDenylistAllowlist:
    """Denylist takes precedence over allowlist (Requirements 9.4, 9.5)."""

    def test_denylist_blocks_command(self):
        policy = TerminalPolicy(denylist=["curl"])
        result = policy.validate_command("curl http://evil.com")
        assert result.blocked is True
        assert "denylist" in result.block_reason

    def test_allowlist_permits_command(self):
        policy = TerminalPolicy(allowlist=["git", "npm"])
        result = policy.validate_command("git push origin main")
        assert result.allowed is True

    def test_allowlist_blocks_unlisted_command(self):
        policy = TerminalPolicy(allowlist=["git", "npm"])
        result = policy.validate_command("wget http://example.com")
        assert result.blocked is True
        assert "not in allowlist" in result.block_reason

    def test_denylist_precedence_over_allowlist(self):
        """If a command matches both denylist and allowlist, denylist wins."""
        policy = TerminalPolicy(
            allowlist=["curl"],
            denylist=["curl"],
        )
        result = policy.validate_command("curl http://example.com")
        assert result.blocked is True
        assert "denylist" in result.block_reason

    def test_empty_allowlist_allows_all(self):
        """An empty allowlist means no allowlist filtering is applied."""
        policy = TerminalPolicy(allowlist=[])
        result = policy.validate_command("echo hello")
        assert result.allowed is True

    def test_empty_denylist_blocks_nothing(self):
        policy = TerminalPolicy(denylist=[])
        result = policy.validate_command("echo hello")
        assert result.allowed is True

    def test_denylist_case_insensitive(self):
        policy = TerminalPolicy(denylist=["WGET"])
        result = policy.validate_command("wget http://example.com")
        assert result.blocked is True

    def test_allowlist_case_insensitive(self):
        policy = TerminalPolicy(allowlist=["GIT"])
        result = policy.validate_command("git status")
        assert result.allowed is True


class TestListSizeLimits:
    """Lists are capped at 500 entries (Requirement 9.5)."""

    def test_denylist_truncated_to_500(self):
        entries = [f"cmd_{i}" for i in range(600)]
        policy = TerminalPolicy(denylist=entries)
        assert len(policy.denylist) == MAX_LIST_ENTRIES

    def test_allowlist_truncated_to_500(self):
        entries = [f"cmd_{i}" for i in range(600)]
        policy = TerminalPolicy(allowlist=entries)
        assert len(policy.allowlist) == MAX_LIST_ENTRIES

    def test_set_denylist_truncates(self):
        policy = TerminalPolicy()
        entries = [f"cmd_{i}" for i in range(600)]
        policy.set_denylist(entries)
        assert len(policy.denylist) == MAX_LIST_ENTRIES

    def test_set_allowlist_truncates(self):
        policy = TerminalPolicy()
        entries = [f"cmd_{i}" for i in range(600)]
        policy.set_allowlist(entries)
        assert len(policy.allowlist) == MAX_LIST_ENTRIES


class TestAllowedFolders:
    """Commands referencing paths outside allowed folders are rejected (Requirement 9.3)."""

    def test_no_allowed_folders_permits_all(self):
        """If no allowed_folders configured, all paths are permitted."""
        policy = TerminalPolicy(allowed_folders=[])
        result = policy.validate_command("cat /etc/passwd", working_directory="/tmp")
        assert result.allowed is True

    def test_working_directory_within_allowed(self, tmp_path):
        allowed = str(tmp_path / "project")
        (tmp_path / "project").mkdir()
        policy = TerminalPolicy(allowed_folders=[allowed])
        result = policy.validate_command("ls", working_directory=allowed)
        assert result.allowed is True

    def test_working_directory_outside_allowed(self, tmp_path):
        allowed = str(tmp_path / "project")
        (tmp_path / "project").mkdir()
        outside = str(tmp_path / "other")
        (tmp_path / "other").mkdir()
        policy = TerminalPolicy(allowed_folders=[allowed])
        result = policy.validate_command("ls", working_directory=outside)
        assert result.blocked is True
        assert "path is not permitted" in result.block_reason

    def test_subdirectory_of_allowed_folder_permitted(self, tmp_path):
        allowed = str(tmp_path / "project")
        sub = tmp_path / "project" / "src"
        sub.mkdir(parents=True)
        policy = TerminalPolicy(allowed_folders=[allowed])
        result = policy.validate_command("ls", working_directory=str(sub))
        assert result.allowed is True

    def test_absolute_path_in_command_outside_allowed(self, tmp_path):
        allowed = str(tmp_path / "project")
        (tmp_path / "project").mkdir()
        policy = TerminalPolicy(allowed_folders=[allowed])
        result = policy.validate_command(f"cat /etc/passwd", working_directory=allowed)
        assert result.blocked is True
        assert "path is not permitted" in result.block_reason

    def test_absolute_path_in_command_within_allowed(self, tmp_path):
        allowed = str(tmp_path / "project")
        target = tmp_path / "project" / "file.txt"
        (tmp_path / "project").mkdir()
        target.touch()
        policy = TerminalPolicy(allowed_folders=[allowed])
        result = policy.validate_command(f"cat {target}", working_directory=allowed)
        assert result.allowed is True

    def test_multiple_allowed_folders(self, tmp_path):
        folder_a = str(tmp_path / "a")
        folder_b = str(tmp_path / "b")
        (tmp_path / "a").mkdir()
        (tmp_path / "b").mkdir()
        policy = TerminalPolicy(allowed_folders=[folder_a, folder_b])
        result_a = policy.validate_command("ls", working_directory=folder_a)
        result_b = policy.validate_command("ls", working_directory=folder_b)
        assert result_a.allowed is True
        assert result_b.allowed is True

    def test_set_allowed_folders_updates(self, tmp_path):
        folder_a = str(tmp_path / "a")
        folder_b = str(tmp_path / "b")
        (tmp_path / "a").mkdir()
        (tmp_path / "b").mkdir()
        policy = TerminalPolicy(allowed_folders=[folder_a])
        policy.set_allowed_folders([folder_b])
        result = policy.validate_command("ls", working_directory=folder_a)
        assert result.blocked is True
        result = policy.validate_command("ls", working_directory=folder_b)
        assert result.allowed is True


class TestValidationResult:
    """ValidationResult dataclass behavior."""

    def test_default_result_is_allowed(self):
        result = ValidationResult(allowed=True)
        assert result.allowed is True
        assert result.blocked is False
        assert result.block_reason is None
        assert result.matched_pattern is None
        assert result.warnings == []

    def test_blocked_result_has_reason(self):
        result = ValidationResult(
            allowed=False,
            blocked=True,
            block_reason="test reason",
        )
        assert result.allowed is False
        assert result.blocked is True
        assert result.block_reason == "test reason"
