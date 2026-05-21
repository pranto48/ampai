"""Unit tests for services/confirmation_token.py.

Validates:
- Valid token passes validation
- Expired token fails
- Changed command fails
- Changed working_directory fails
- Changed browser action fails
- Tampered token fails
"""

import sys
import os
import time
from unittest.mock import patch

import pytest

# Ensure project root is on path
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, _project_root)

# Import directly to avoid services/__init__.py import chain
import importlib.util
_module_path = os.path.join(_project_root, "services", "confirmation_token.py")
_spec = importlib.util.spec_from_file_location("services.confirmation_token", _module_path)
_module = importlib.util.module_from_spec(_spec)
sys.modules["services.confirmation_token"] = _module
_spec.loader.exec_module(_module)

ConfirmationToken = _module.ConfirmationToken
ConfirmationTokenService = _module.ConfirmationTokenService
ValidationResult = _module.ValidationResult
TOKEN_TTL_SECONDS = _module.TOKEN_TTL_SECONDS


@pytest.fixture
def service():
    """Create a ConfirmationTokenService with a test secret."""
    return ConfirmationTokenService(secret="test-secret-for-unit-tests")


# ---------------------------------------------------------------------------
# Terminal token tests
# ---------------------------------------------------------------------------


class TestTerminalTokenValid:
    """Valid terminal token passes validation."""

    def test_valid_token_passes(self, service):
        """A freshly created token validates successfully."""
        token = service.create_terminal_token(
            username="alice",
            session_id="sess-1",
            command="git status",
            working_directory="/home/alice/project",
            shell_type="bash",
        )

        result = service.validate_terminal_token(
            token=token,
            username="alice",
            session_id="sess-1",
            command="git status",
            working_directory="/home/alice/project",
            shell_type="bash",
        )

        assert result.valid is True
        assert result.reason == "Token is valid"
        assert result.expired is False
        assert result.mismatch_field is None

    def test_token_has_correct_fields(self, service):
        """Token contains all expected binding fields."""
        token = service.create_terminal_token(
            username="bob",
            session_id="sess-2",
            command="ls -la",
            working_directory="/tmp",
            shell_type="zsh",
        )

        assert token.username == "bob"
        assert token.session_id == "sess-2"
        assert token.action_type == "terminal"
        assert token.working_directory == "/tmp"
        assert token.shell_type == "zsh"
        assert token.command_hash != ""
        assert token.signature != ""
        assert token.created_at > 0


class TestTerminalTokenExpired:
    """Expired terminal token fails validation."""

    def test_expired_token_rejected(self, service):
        """Token older than 60 seconds is rejected."""
        token = service.create_terminal_token(
            username="alice",
            session_id="sess-1",
            command="echo hello",
            working_directory="/home",
            shell_type="bash",
        )

        # Simulate token being 61 seconds old
        token.created_at = time.time() - 61
        # Re-sign with the old timestamp (simulating a legitimately old token)
        token.signature = service._compute_signature(token)

        result = service.validate_terminal_token(
            token=token,
            username="alice",
            session_id="sess-1",
            command="echo hello",
            working_directory="/home",
            shell_type="bash",
        )

        assert result.valid is False
        assert result.expired is True
        assert "expired" in result.reason.lower()


class TestTerminalTokenCommandMismatch:
    """Changed command fails validation."""

    def test_different_command_rejected(self, service):
        """Token for command_a does not authorize command_b."""
        token = service.create_terminal_token(
            username="alice",
            session_id="sess-1",
            command="git status",
            working_directory="/home",
            shell_type="bash",
        )

        result = service.validate_terminal_token(
            token=token,
            username="alice",
            session_id="sess-1",
            command="rm -rf /home",  # Different command!
            working_directory="/home",
            shell_type="bash",
        )

        assert result.valid is False
        assert result.mismatch_field == "command_hash"
        assert "command" in result.reason.lower()

    def test_slightly_different_command_rejected(self, service):
        """Even a small change in command is detected."""
        token = service.create_terminal_token(
            username="alice",
            session_id="sess-1",
            command="echo hello",
            working_directory="/home",
            shell_type="bash",
        )

        result = service.validate_terminal_token(
            token=token,
            username="alice",
            session_id="sess-1",
            command="echo hello ",  # Trailing space
            working_directory="/home",
            shell_type="bash",
        )

        assert result.valid is False
        assert result.mismatch_field == "command_hash"


class TestTerminalTokenWorkingDirectoryMismatch:
    """Changed working_directory fails validation."""

    def test_different_directory_rejected(self, service):
        """Token bound to one directory rejects execution in another."""
        token = service.create_terminal_token(
            username="alice",
            session_id="sess-1",
            command="ls",
            working_directory="/home/alice",
            shell_type="bash",
        )

        result = service.validate_terminal_token(
            token=token,
            username="alice",
            session_id="sess-1",
            command="ls",
            working_directory="/etc",  # Different directory!
            shell_type="bash",
        )

        assert result.valid is False
        assert result.mismatch_field == "working_directory"


class TestTerminalTokenTampered:
    """Tampered token fails validation."""

    def test_modified_signature_rejected(self, service):
        """Token with modified signature is rejected."""
        token = service.create_terminal_token(
            username="alice",
            session_id="sess-1",
            command="echo safe",
            working_directory="/home",
            shell_type="bash",
        )

        # Tamper with the signature
        token.signature = "0" * 64

        result = service.validate_terminal_token(
            token=token,
            username="alice",
            session_id="sess-1",
            command="echo safe",
            working_directory="/home",
            shell_type="bash",
        )

        assert result.valid is False
        assert "tampered" in result.reason.lower()

    def test_modified_username_in_token_rejected(self, service):
        """Token with modified username field is detected via signature."""
        token = service.create_terminal_token(
            username="alice",
            session_id="sess-1",
            command="echo safe",
            working_directory="/home",
            shell_type="bash",
        )

        # Tamper with the username field (signature won't match)
        token.username = "mallory"

        result = service.validate_terminal_token(
            token=token,
            username="mallory",
            session_id="sess-1",
            command="echo safe",
            working_directory="/home",
            shell_type="bash",
        )

        assert result.valid is False
        assert "tampered" in result.reason.lower() or "signature" in result.reason.lower()


# ---------------------------------------------------------------------------
# Browser token tests
# ---------------------------------------------------------------------------


class TestBrowserTokenValid:
    """Valid browser token passes validation."""

    def test_valid_browser_token_passes(self, service):
        """A freshly created browser token validates successfully."""
        token = service.create_browser_token(
            username="alice",
            session_id="sess-1",
            action_type="submit",
            target_url="https://example.com/form",
            element_selector="#submit-btn",
        )

        result = service.validate_browser_token(
            token=token,
            username="alice",
            session_id="sess-1",
            action_type="submit",
            target_url="https://example.com/form",
            element_selector="#submit-btn",
        )

        assert result.valid is True


class TestBrowserTokenActionMismatch:
    """Changed browser action fails validation."""

    def test_different_action_type_rejected(self, service):
        """Token for 'submit' does not authorize 'navigate'."""
        token = service.create_browser_token(
            username="alice",
            session_id="sess-1",
            action_type="submit",
            target_url="https://example.com/form",
            element_selector="#submit-btn",
        )

        result = service.validate_browser_token(
            token=token,
            username="alice",
            session_id="sess-1",
            action_type="navigate",  # Different action!
            target_url="https://example.com/form",
            element_selector="#submit-btn",
        )

        assert result.valid is False
        assert result.mismatch_field == "action_type"

    def test_different_target_url_rejected(self, service):
        """Token for one URL does not authorize a different URL."""
        token = service.create_browser_token(
            username="alice",
            session_id="sess-1",
            action_type="navigate",
            target_url="https://safe.com",
            element_selector="",
        )

        result = service.validate_browser_token(
            token=token,
            username="alice",
            session_id="sess-1",
            action_type="navigate",
            target_url="https://evil.com",  # Different URL!
            element_selector="",
        )

        assert result.valid is False
        assert result.mismatch_field == "target_url"

    def test_different_selector_rejected(self, service):
        """Token for one selector does not authorize a different selector."""
        token = service.create_browser_token(
            username="alice",
            session_id="sess-1",
            action_type="click",
            target_url="https://example.com",
            element_selector="#safe-button",
        )

        result = service.validate_browser_token(
            token=token,
            username="alice",
            session_id="sess-1",
            action_type="click",
            target_url="https://example.com",
            element_selector="#delete-all-button",  # Different selector!
        )

        assert result.valid is False
        assert result.mismatch_field == "element_selector"


class TestBrowserTokenExpired:
    """Expired browser token fails validation."""

    def test_expired_browser_token_rejected(self, service):
        """Browser token older than 60 seconds is rejected."""
        token = service.create_browser_token(
            username="alice",
            session_id="sess-1",
            action_type="submit",
            target_url="https://example.com",
            element_selector="#form",
        )

        # Simulate 61 seconds old
        token.created_at = time.time() - 61
        token.signature = service._compute_signature(token)

        result = service.validate_browser_token(
            token=token,
            username="alice",
            session_id="sess-1",
            action_type="submit",
            target_url="https://example.com",
            element_selector="#form",
        )

        assert result.valid is False
        assert result.expired is True


# ---------------------------------------------------------------------------
# Token serialization tests
# ---------------------------------------------------------------------------


class TestTokenSerialization:
    """Token to_dict/from_dict round-trip."""

    def test_round_trip(self, service):
        """Token survives serialization and deserialization."""
        token = service.create_terminal_token(
            username="alice",
            session_id="sess-1",
            command="echo test",
            working_directory="/home",
            shell_type="bash",
        )

        data = token.to_dict()
        restored = ConfirmationToken.from_dict(data)

        assert restored.username == token.username
        assert restored.session_id == token.session_id
        assert restored.command_hash == token.command_hash
        assert restored.signature == token.signature
        assert restored.created_at == token.created_at

        # Validate the restored token
        result = service.validate_terminal_token(
            token=restored,
            username="alice",
            session_id="sess-1",
            command="echo test",
            working_directory="/home",
            shell_type="bash",
        )
        assert result.valid is True


# ---------------------------------------------------------------------------
# Production secret enforcement
# ---------------------------------------------------------------------------


class TestSecretEnforcement:
    """Production secret validation."""

    def test_weak_secret_rejected_in_production(self):
        """Weak/default secrets are rejected in production mode."""
        with patch.dict(os.environ, {"AMPAI_ENV": "production", "JWT_SECRET": "change-me"}):
            with pytest.raises(ValueError, match="Refusing to use weak"):
                ConfirmationTokenService(secret="change-me")

    def test_weak_secret_allowed_in_development(self):
        """Weak secrets are allowed in development mode."""
        with patch.dict(os.environ, {"AMPAI_ENV": "development"}):
            # Should not raise
            svc = ConfirmationTokenService(secret="change-me")
            assert svc is not None
