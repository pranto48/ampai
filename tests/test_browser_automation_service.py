"""Tests for services/browser_automation_service.py.

Validates the BrowserAutomationService:
- Disabled-by-default enforcement (Requirement 8.2)
- Domain allowlist enforcement (Requirements 8.3, 8.10)
- Confirmation flow (Requirements 8.4, 8.5)
- 30-second action timeout (Requirement 8.7)
- Forbidden operations refusal (Requirement 8.8)
- User-provided credentials only (Requirement 8.9)
- Audit logging (Requirement 8.6)
"""

import asyncio
import os
import sys
import importlib.util
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Import browser_automation_service directly to avoid heavy dependency chain
_service_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "services",
    "browser_automation_service.py",
)
_spec = importlib.util.spec_from_file_location(
    "services.browser_automation_service", _service_path
)
_module = importlib.util.module_from_spec(_spec)
sys.modules["services.browser_automation_service"] = _module
_spec.loader.exec_module(_module)

BrowserActionResult = _module.BrowserActionResult
BrowserActionStatus = _module.BrowserActionStatus
BrowserAutomationService = _module.BrowserAutomationService
BrowserConfig = _module.BrowserConfig
BrowserDisabledError = _module.BrowserDisabledError
BrowserForbiddenOperationError = _module.BrowserForbiddenOperationError
BrowserTimeoutError = _module.BrowserTimeoutError


# Helper to run async functions in tests
def run_async(coro):
    """Run an async coroutine synchronously."""
    return asyncio.get_event_loop().run_until_complete(coro)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def disabled_config():
    """A disabled-by-default browser config."""
    return BrowserConfig(enabled=False)


@pytest.fixture
def enabled_config():
    """An enabled browser config with a domain allowlist."""
    return BrowserConfig(
        enabled=True,
        headless=False,
        domain_allowlist=["example.com", "test.org"],
    )


@pytest.fixture
def mock_audit_logger():
    """A mock AuditLogger."""
    return MagicMock()


@pytest.fixture
def mock_browser_policy():
    """A mock BrowserPolicy that allows example.com and test.org."""
    from policy.browser_policy import BrowserPolicy
    return BrowserPolicy(domain_allowlist=["example.com", "test.org"])


@pytest.fixture
def service(enabled_config, mock_audit_logger, mock_browser_policy):
    """A fully configured BrowserAutomationService."""
    return BrowserAutomationService(
        config=enabled_config,
        audit_logger=mock_audit_logger,
        browser_policy=mock_browser_policy,
    )


@pytest.fixture
def disabled_service(disabled_config, mock_audit_logger):
    """A disabled BrowserAutomationService."""
    return BrowserAutomationService(
        config=disabled_config,
        audit_logger=mock_audit_logger,
    )


# ---------------------------------------------------------------------------
# Test: Disabled by default (Requirement 8.2)
# ---------------------------------------------------------------------------


class TestCheckEnabled:
    """Browser automation is disabled by default."""

    def test_disabled_raises_error(self, disabled_service):
        with pytest.raises(BrowserDisabledError):
            disabled_service.check_enabled()

    def test_enabled_does_not_raise(self, service):
        service.check_enabled()  # Should not raise

    def test_open_when_disabled_raises(self, disabled_service):
        with pytest.raises(BrowserDisabledError):
            run_async(disabled_service.open_browser(username="user1"))

    def test_navigate_when_disabled_raises(self, disabled_service):
        with pytest.raises(BrowserDisabledError):
            run_async(disabled_service.navigate(
                "https://example.com", username="user1"
            ))

    def test_click_when_disabled_raises(self, disabled_service):
        with pytest.raises(BrowserDisabledError):
            run_async(disabled_service.click("#btn", username="user1"))

    def test_close_when_disabled_raises(self, disabled_service):
        with pytest.raises(BrowserDisabledError):
            run_async(disabled_service.close(username="user1"))

    def test_default_config_from_env_disabled(self):
        """Default config reads BROWSER_AUTOMATION_ENABLED=false from env."""
        with patch.dict(os.environ, {"BROWSER_AUTOMATION_ENABLED": "false"}):
            svc = BrowserAutomationService()
            assert svc.config.enabled is False

    def test_config_from_env_enabled(self):
        """Config reads BROWSER_AUTOMATION_ENABLED=true from env."""
        with patch.dict(os.environ, {"BROWSER_AUTOMATION_ENABLED": "true"}):
            svc = BrowserAutomationService()
            assert svc.config.enabled is True


# ---------------------------------------------------------------------------
# Test: Domain allowlist enforcement (Requirements 8.3, 8.10)
# ---------------------------------------------------------------------------


class TestDomainAllowlist:
    """Domain allowlist blocks navigation to non-permitted domains."""

    def test_allowed_domain_passes(self, service):
        # Should not raise
        service.check_domain("https://example.com/page")

    def test_subdomain_allowed(self, service):
        # Subdomains of allowed domains should pass
        service.check_domain("https://sub.example.com/page")

    def test_blocked_domain_raises(self, service):
        from policy.browser_policy import BrowserPolicyError
        with pytest.raises(BrowserPolicyError):
            service.check_domain("https://evil.com/hack")

    def test_empty_allowlist_blocks_all(self, mock_audit_logger):
        from policy.browser_policy import BrowserPolicy, BrowserPolicyError
        policy = BrowserPolicy(domain_allowlist=[])
        svc = BrowserAutomationService(
            config=BrowserConfig(enabled=True),
            audit_logger=mock_audit_logger,
            browser_policy=policy,
        )
        with pytest.raises(BrowserPolicyError):
            svc.check_domain("https://anything.com")

    def test_navigate_blocked_domain_returns_blocked(self, service):
        result = run_async(service.navigate(
            "https://evil.com/hack", username="user1"
        ))
        assert result.status == BrowserActionStatus.BLOCKED
        assert "not in the permitted allowlist" in result.message


# ---------------------------------------------------------------------------
# Test: Forbidden operations (Requirement 8.8)
# ---------------------------------------------------------------------------


class TestForbiddenOperations:
    """Refuse password reading, MFA/captcha bypass, paywall bypass."""

    def test_password_reading_refused(self, service):
        with pytest.raises(BrowserForbiddenOperationError):
            service._check_forbidden_operation("extract", "saved password field")

    def test_mfa_bypass_refused(self, service):
        with pytest.raises(BrowserForbiddenOperationError):
            service._check_forbidden_operation("click", "mfa bypass button")

    def test_captcha_bypass_refused(self, service):
        with pytest.raises(BrowserForbiddenOperationError):
            service._check_forbidden_operation("submit", "captcha bypass form")

    def test_paywall_bypass_refused(self, service):
        with pytest.raises(BrowserForbiddenOperationError):
            service._check_forbidden_operation("navigate", "paywall bypass url")

    def test_normal_operation_allowed(self, service):
        # Should not raise
        service._check_forbidden_operation("click", "#submit-button")
        service._check_forbidden_operation("navigate", "https://example.com")
        service._check_forbidden_operation("extract", ".article-content")


# ---------------------------------------------------------------------------
# Test: Confirmation flow (Requirements 8.4, 8.5)
# ---------------------------------------------------------------------------


class TestConfirmationFlow:
    """Confirmation flow: request, approve, deny, timeout."""

    def test_request_confirmation_returns_pending(self, service):
        result = run_async(service.request_confirmation(
            "action-1", "Navigate to example.com"
        ))
        assert result.status == BrowserActionStatus.CONFIRMATION_REQUIRED
        assert "action-1" in result.data["action_id"]

    def test_approve_action_sets_result(self, service):
        run_async(service.request_confirmation("action-2", "Click button"))
        service.approve_action("action-2")
        approved = run_async(service.wait_for_confirmation("action-2"))
        assert approved is True

    def test_deny_action_sets_result(self, service):
        run_async(service.request_confirmation("action-3", "Submit form"))
        service.deny_action("action-3")
        approved = run_async(service.wait_for_confirmation("action-3"))
        assert approved is False

    def test_timeout_returns_false(self, service):
        """Confirmation timeout returns False (Requirement 8.5)."""
        service.confirmation_timeout = 0.1  # 100ms for test speed
        run_async(service.request_confirmation("action-4", "Extract data"))
        approved = run_async(service.wait_for_confirmation("action-4"))
        assert approved is False

    def test_wait_for_unknown_action_returns_false(self, service):
        approved = run_async(service.wait_for_confirmation("nonexistent"))
        assert approved is False


# ---------------------------------------------------------------------------
# Test: User-provided credentials (Requirement 8.9)
# ---------------------------------------------------------------------------


class TestCredentials:
    """Only user-provided credentials allowed for login automation."""

    def test_password_field_without_credentials_blocked(self, service):
        """Typing into password field without credentials_provided is blocked."""
        # Mock the browser to avoid actual Playwright calls
        service._browser = MagicMock()
        service._page = MagicMock()
        service._context = MagicMock()

        result = run_async(service.type_text(
            selector="input[type=password]",
            text="secret123",
            username="user1",
            credentials_provided=False,
        ))
        assert result.status == BrowserActionStatus.BLOCKED
        assert "user-provided credentials" in result.message

    def test_password_field_with_credentials_allowed(self, service):
        """Typing into password field with credentials_provided is allowed."""
        # Mock the browser
        service._browser = MagicMock()
        mock_page = AsyncMock()
        mock_page.url = "https://example.com/login"
        mock_page.fill = AsyncMock()
        mock_page.is_closed = MagicMock(return_value=False)
        service._page = mock_page
        service._context = MagicMock()

        result = run_async(service.type_text(
            selector="input[type=password]",
            text="secret123",
            username="user1",
            credentials_provided=True,
        ))
        assert result.status == BrowserActionStatus.SUCCESS


# ---------------------------------------------------------------------------
# Test: Audit logging (Requirement 8.6)
# ---------------------------------------------------------------------------


class TestAuditLogging:
    """Each action is logged to AuditLogger."""

    def test_navigate_blocked_logs_audit(self, service, mock_audit_logger):
        run_async(service.navigate(
            "https://evil.com", username="user1", session_id="s1"
        ))
        mock_audit_logger.log.assert_called_once()
        call_kwargs = mock_audit_logger.log.call_args[1]
        assert call_kwargs["username"] == "user1"
        assert call_kwargs["session_id"] == "s1"
        assert call_kwargs["category"] == "browser"
        assert "blocked" in call_kwargs["details"]["outcome"]

    def test_open_browser_logs_audit(self, service, mock_audit_logger):
        """Open browser logs to audit (mocked Playwright)."""
        # Patch _ensure_browser directly to avoid import chain issues
        async def mock_ensure():
            service._browser = MagicMock()
            service._context = MagicMock()
            service._page = MagicMock()

        service._ensure_browser = mock_ensure

        result = run_async(service.open_browser(
            username="user1", session_id="s1"
        ))
        assert result.status == BrowserActionStatus.SUCCESS
        mock_audit_logger.log.assert_called_once()
        call_kwargs = mock_audit_logger.log.call_args[1]
        assert call_kwargs["details"]["action"] == "open"
        assert call_kwargs["details"]["outcome"] == "success"

    def test_no_audit_logger_does_not_crash(self, enabled_config, mock_browser_policy):
        """Service works without an audit logger."""
        svc = BrowserAutomationService(
            config=enabled_config,
            audit_logger=None,
            browser_policy=mock_browser_policy,
        )
        # _log_action should not raise
        svc._log_action("user1", "test", "target", "success")


# ---------------------------------------------------------------------------
# Test: Action dispatcher (Requirement 8.1)
# ---------------------------------------------------------------------------


class TestExecuteAction:
    """execute_action dispatches to the correct method."""

    def test_unknown_action_returns_failed(self, service):
        result = run_async(service.execute_action(
            action="unknown_action", username="user1"
        ))
        assert result.status == BrowserActionStatus.FAILED
        assert "Unknown action" in result.message

    def test_navigate_without_url_returns_failed(self, service):
        result = run_async(service.execute_action(
            action="navigate", username="user1"
        ))
        assert result.status == BrowserActionStatus.FAILED
        assert "URL is required" in result.message

    def test_click_without_selector_returns_failed(self, service):
        result = run_async(service.execute_action(
            action="click", username="user1"
        ))
        assert result.status == BrowserActionStatus.FAILED
        assert "Selector is required" in result.message

    def test_type_without_value_returns_failed(self, service):
        result = run_async(service.execute_action(
            action="type", username="user1", selector="#input"
        ))
        assert result.status == BrowserActionStatus.FAILED
        assert "value are required" in result.message

    def test_submit_without_selector_returns_failed(self, service):
        result = run_async(service.execute_action(
            action="submit", username="user1"
        ))
        assert result.status == BrowserActionStatus.FAILED
        assert "Selector is required" in result.message


# ---------------------------------------------------------------------------
# Test: Headed browser default (Requirement 8.6)
# ---------------------------------------------------------------------------


class TestHeadedDefault:
    """Browser uses headed mode by default."""

    def test_default_headless_false(self):
        config = BrowserConfig()
        assert config.headless is False

    def test_env_headless_false(self):
        with patch.dict(os.environ, {"BROWSER_HEADLESS": "false"}):
            svc = BrowserAutomationService()
            assert svc.config.headless is False

    def test_env_headless_true(self):
        with patch.dict(os.environ, {"BROWSER_HEADLESS": "true"}):
            svc = BrowserAutomationService()
            assert svc.config.headless is True
