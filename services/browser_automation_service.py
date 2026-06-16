"""
Browser Automation Service — Playwright-based browser control with security enforcement.

Provides the BrowserAutomationService class that performs controlled browser actions
on behalf of the user. Enforces disabled-by-default, domain allowlist, confirmation
flow, action timeout, and refuses dangerous operations.

Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7, 8.8, 8.9, 8.10
"""

from __future__ import annotations

import asyncio
import base64
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from logging_utils import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ACTION_TIMEOUT_SECONDS = 30
CONFIRMATION_TIMEOUT_SECONDS = 60


# Patterns that indicate forbidden operations (Requirement 8.8)
FORBIDDEN_OPERATIONS = [
    "password",
    "saved password",
    "stored password",
    "credential export",
    "mfa bypass",
    "captcha bypass",
    "paywall bypass",
    "access control bypass",
    "2fa bypass",
    "two-factor bypass",
]


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


class BrowserActionStatus(str, Enum):
    """Status of a browser action."""

    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    DENIED = "denied"
    CANCELLED = "cancelled"
    CONFIRMATION_REQUIRED = "confirmation_required"
    DISABLED = "disabled"
    BLOCKED = "blocked"


@dataclass
class BrowserConfig:
    """Configuration for browser automation."""

    enabled: bool = False
    headless: bool = False
    domain_allowlist: List[str] = field(default_factory=list)
    encryption_key: Optional[str] = None


@dataclass
class BrowserActionResult:
    """Result of a browser action."""

    action: str
    status: str
    message: str = ""
    data: Optional[Any] = None
    url: Optional[str] = None
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    duration_ms: int = 0


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class BrowserDisabledError(Exception):
    """Raised when browser automation is disabled."""

    pass


class BrowserTimeoutError(Exception):
    """Raised when a browser action exceeds the timeout."""

    pass


class BrowserConfirmationDeniedError(Exception):
    """Raised when user denies a browser action confirmation."""

    pass


class BrowserForbiddenOperationError(Exception):
    """Raised when a forbidden operation is attempted."""

    pass


# ---------------------------------------------------------------------------
# BrowserAutomationService
# ---------------------------------------------------------------------------


class BrowserAutomationService:
    """
    Playwright-based browser automation with security enforcement.

    Security features:
    - Disabled by default (BROWSER_AUTOMATION_ENABLED=false)
    - Headed browser by default (BROWSER_HEADLESS=false)
    - Domain allowlist enforcement (empty = block all)
    - Confirmation flow with 60s timeout
    - 30-second action timeout
    - Refuses password reading, MFA/captcha bypass, paywall bypass
    - Uses only user-provided credentials for login
    - Logs all actions to AuditLogger
    """

    def __init__(
        self,
        config: Optional[BrowserConfig] = None,
        audit_logger=None,
        browser_policy=None,
    ):
        """
        Initialize BrowserAutomationService.

        Args:
            config: BrowserConfig instance. If None, reads from env vars.
            audit_logger: AuditLogger instance for action logging.
            browser_policy: BrowserPolicy instance for domain validation.
        """
        if config is None:
            config = BrowserConfig(
                enabled=os.getenv(
                    "BROWSER_AUTOMATION_ENABLED", "false"
                ).lower() == "true",
                headless=os.getenv(
                    "BROWSER_HEADLESS", "false"
                ).lower() == "true",
                domain_allowlist=[],
            )

        self.config = config
        self.audit_logger = audit_logger
        self.action_timeout = ACTION_TIMEOUT_SECONDS
        self.confirmation_timeout = CONFIRMATION_TIMEOUT_SECONDS
        self._browser = None
        self._context = None
        self._page = None

        # Use provided policy or create one from config
        if browser_policy is not None:
            self._policy = browser_policy
        else:
            from policy.browser_policy import BrowserPolicy
            self._policy = BrowserPolicy(config.domain_allowlist)

        # Pending confirmations: action_id -> asyncio.Event
        self._pending_confirmations: Dict[str, asyncio.Event] = {}
        self._confirmation_results: Dict[str, bool] = {}

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------

    def check_enabled(self) -> None:
        """Raise BrowserDisabledError if browser automation is disabled.

        Requirement 8.2: disabled by default, must be explicitly enabled.
        """
        if not self.config.enabled:
            raise BrowserDisabledError(
                "Browser automation is disabled. "
                "Set BROWSER_AUTOMATION_ENABLED=true to enable."
            )

    def check_domain(self, url: str) -> None:
        """Validate URL against domain allowlist via BrowserPolicy.

        Requirement 8.3, 8.10: only navigate to allowed domains.
        """
        self._policy.check_domain(url)

    def _check_forbidden_operation(
        self, action: str, target: str = "", allow_credential_input: bool = False
    ) -> None:
        """Refuse password reading, MFA/captcha bypass, paywall bypass.

        Requirement 8.8: refuse dangerous operations.

        Args:
            action: The browser action being performed.
            target: The target element/URL.
            allow_credential_input: If True, skip password-field checks
                (used when user provides credentials for login automation).
        """
        combined = f"{action} {target}".lower()
        for pattern in FORBIDDEN_OPERATIONS:
            if pattern in combined:
                # Allow typing into password fields for login automation
                # (Requirement 8.9). The credential check in type_text
                # handles whether credentials are user-provided.
                if pattern == "password" and action.lower() == "type":
                    continue
                # Allow credential input when explicitly flagged
                if allow_credential_input and pattern == "password":
                    continue
                raise BrowserForbiddenOperationError(
                    f"Operation refused: '{pattern}' operations are not permitted. "
                    "Browser automation cannot read passwords, bypass MFA/captcha, "
                    "or bypass paywalls/access controls."
                )

    # ------------------------------------------------------------------
    # Confirmation flow
    # ------------------------------------------------------------------

    async def request_confirmation(
        self, action_id: str, action_description: str
    ) -> BrowserActionResult:
        """
        Request user confirmation for a browser action.

        Requirement 8.4: present action and wait up to 60s for approval.
        Requirement 8.5: cancel on timeout or denial.

        Returns a result with status confirmation_required. The caller
        should then call approve_action() or deny_action() within 60s.
        """
        event = asyncio.Event()
        self._pending_confirmations[action_id] = event
        self._confirmation_results[action_id] = False

        return BrowserActionResult(
            action="confirmation_request",
            status=BrowserActionStatus.CONFIRMATION_REQUIRED,
            message=f"Confirmation required: {action_description}. "
            f"Approve within {self.confirmation_timeout}s.",
            data={"action_id": action_id, "description": action_description},
        )

    async def wait_for_confirmation(self, action_id: str) -> bool:
        """
        Wait for user to approve or deny an action.

        Returns True if approved, False if denied or timed out.
        """
        event = self._pending_confirmations.get(action_id)
        if event is None:
            return False

        try:
            await asyncio.wait_for(
                event.wait(), timeout=self.confirmation_timeout
            )
            return self._confirmation_results.get(action_id, False)
        except asyncio.TimeoutError:
            logger.info(
                "Confirmation timeout for action %s", action_id
            )
            return False
        finally:
            self._pending_confirmations.pop(action_id, None)
            self._confirmation_results.pop(action_id, None)

    def approve_action(self, action_id: str) -> None:
        """Approve a pending browser action."""
        if action_id in self._pending_confirmations:
            self._confirmation_results[action_id] = True
            self._pending_confirmations[action_id].set()

    def deny_action(self, action_id: str) -> None:
        """Deny a pending browser action."""
        if action_id in self._pending_confirmations:
            self._confirmation_results[action_id] = False
            self._pending_confirmations[action_id].set()

    # ------------------------------------------------------------------
    # Audit logging helper
    # ------------------------------------------------------------------

    def _log_action(
        self,
        username: str,
        action: str,
        target: str,
        outcome: str,
        session_id: Optional[str] = None,
    ) -> None:
        """Log a browser action to the AuditLogger.

        Requirement 8.6: log action type, target URL/element, timestamp, outcome.
        """
        if self.audit_logger is None:
            return

        try:
            from core.audit import ACTION_BROWSER_ACTION, ACTION_BROWSER_NAVIGATE

            action_type = (
                ACTION_BROWSER_NAVIGATE
                if action in ("navigate", "open")
                else ACTION_BROWSER_ACTION
            )

            self.audit_logger.log(
                username=username,
                action_type=action_type,
                details={
                    "action": action,
                    "target": target[:500] if target else "",
                    "outcome": outcome,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
                session_id=session_id,
                category="browser",
            )
        except Exception as exc:
            logger.error("Failed to log browser action: %s", exc)

    # ------------------------------------------------------------------
    # Browser lifecycle
    # ------------------------------------------------------------------

    async def _ensure_browser(self) -> None:
        """Launch Playwright browser if not already running."""
        if self._browser is not None and self._page is not None:
            return

        try:
            from playwright.async_api import async_playwright

            pw = await async_playwright().start()
            ws_endpoint = os.getenv("BROWSER_WS_ENDPOINT")
            if ws_endpoint:
                logger.info(f"Connecting to remote browser at: {ws_endpoint}")
                self._browser = await pw.chromium.connect(ws_endpoint)
            else:
                self._browser = await pw.chromium.launch(
                    headless=self.config.headless
                )
            
            from database import get_config
            emulation_mode = (get_config("browser_emulation_mode") or "desktop").strip().lower()
            if emulation_mode == "mobile":
                logger.info("Initializing Playwright with Mobile viewport and UA emulation.")
                self._context = await self._browser.new_context(
                    viewport={"width": 375, "height": 667},
                    device_scale_factor=2,
                    is_mobile=True,
                    has_touch=True,
                    user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"
                )
            else:
                logger.info("Initializing Playwright with Desktop viewport emulation.")
                self._context = await self._browser.new_context(
                    viewport={"width": 1280, "height": 800}
                )
            self._page = await self._context.new_page()
        except Exception as exc:
            logger.error("Failed to launch browser: %s", exc)
            raise

    async def _execute_with_timeout(self, coro_func, action_name: str):
        """Execute a coroutine function with the configured action timeout and retries.

        Requirement 8.7: abort action, close tab, return timeout error
        if action exceeds 30 seconds.
        """
        try:
            import playwright.errors
            from playwright.async_api import Error as PlaywrightError
            playwright_errors = (
                playwright.errors.TimeoutError,
                playwright.errors.Error,
                playwright.errors.TargetClosedError,
                PlaywrightError,
            )
            is_playwright_timeout = lambda e: isinstance(e, playwright.errors.TimeoutError)
        except ImportError:
            class DummyPlaywrightError(Exception):
                pass
            playwright_errors = (DummyPlaywrightError,)
            is_playwright_timeout = lambda e: False

        max_retries = 3
        backoff_factor = 2.0
        initial_delay = 1.0  # seconds

        for attempt in range(1, max_retries + 1):
            try:
                # Ensure the browser/page is open and healthy on each attempt
                await self._ensure_browser()
                if self._page is None or self._page.is_closed():
                    if self._context:
                        self._page = await self._context.new_page()
                    else:
                        self._browser = None
                        await self._ensure_browser()

                # Call the function to get a fresh coroutine
                coro = coro_func()
                return await asyncio.wait_for(coro, timeout=self.action_timeout)

            except (asyncio.TimeoutError,
                    BrowserTimeoutError,
                    *playwright_errors,
                    Exception) as exc:

                logger.warning(
                    "Browser action '%s' failed on attempt %d/%d: %s",
                    action_name,
                    attempt,
                    max_retries,
                    exc,
                )

                # Reset browser client if connection/context was closed/crashed
                if "closed" in str(exc).lower() or "connection" in str(exc).lower() or "shutdown" in str(exc).lower():
                    logger.warning("Premature shutdown or connection loss detected. Resetting browser client.")
                    try:
                        if self._browser:
                            await self._browser.close()
                    except Exception:
                        pass
                    self._browser = None
                    self._context = None
                    self._page = None

                # Clean up / reset the page if it timed out
                if isinstance(exc, (asyncio.TimeoutError, BrowserTimeoutError)) or is_playwright_timeout(exc):
                    try:
                        if self._page and not self._page.is_closed():
                            await self._page.close()
                            if self._context:
                                self._page = await self._context.new_page()
                    except Exception:
                        pass

                if attempt == max_retries:
                    # Final attempt failed
                    if isinstance(exc, (asyncio.TimeoutError, BrowserTimeoutError)) or is_playwright_timeout(exc):
                        raise BrowserTimeoutError(
                            f"Action '{action_name}' timed out after "
                            f"{self.action_timeout} seconds."
                        )
                    raise exc

                # Backoff sleep
                delay = initial_delay * (backoff_factor ** (attempt - 1))
                logger.info(f"Retrying browser action '{action_name}' in {delay:.1f} seconds...")
                await asyncio.sleep(delay)

    # ------------------------------------------------------------------
    # Browser actions
    # ------------------------------------------------------------------

    async def open_browser(self, username: str, session_id: Optional[str] = None) -> BrowserActionResult:
        """
        Open a browser instance.

        Requirement 8.1: open browser action.
        Requirement 8.6: headed browser by default.
        """
        self.check_enabled()
        start = time.time()

        try:
            await self._ensure_browser()
            duration_ms = int((time.time() - start) * 1000)

            self._log_action(
                username=username,
                action="open",
                target="chromium",
                outcome="success",
                session_id=session_id,
            )

            return BrowserActionResult(
                action="open",
                status=BrowserActionStatus.SUCCESS,
                message="Browser opened successfully.",
                data={"headless": self.config.headless},
                duration_ms=duration_ms,
            )
        except Exception as exc:
            duration_ms = int((time.time() - start) * 1000)
            self._log_action(
                username=username,
                action="open",
                target="chromium",
                outcome=f"failed: {str(exc)[:200]}",
                session_id=session_id,
            )
            return BrowserActionResult(
                action="open",
                status=BrowserActionStatus.FAILED,
                message=f"Failed to open browser: {str(exc)[:200]}",
                duration_ms=duration_ms,
            )

    async def navigate(
        self, url: str, username: str, session_id: Optional[str] = None
    ) -> BrowserActionResult:
        """
        Navigate to a URL after domain allowlist check.

        Requirement 8.3, 8.10: validate domain before navigation.
        Requirement 8.7: 30-second timeout.
        """
        self.check_enabled()
        self._check_forbidden_operation("navigate", url)
        start = time.time()

        try:
            self.check_domain(url)
        except Exception as exc:
            duration_ms = int((time.time() - start) * 1000)
            self._log_action(
                username=username,
                action="navigate",
                target=url,
                outcome=f"blocked: {str(exc)[:200]}",
                session_id=session_id,
            )
            return BrowserActionResult(
                action="navigate",
                status=BrowserActionStatus.BLOCKED,
                message=str(exc),
                url=url,
                duration_ms=duration_ms,
            )

        try:
            await self._ensure_browser()

            async def _do_navigate():
                await self._page.goto(url, wait_until="domcontentloaded")
                return self._page.url

            final_url = await self._execute_with_timeout(
                _do_navigate, "navigate"
            )
            duration_ms = int((time.time() - start) * 1000)

            self._log_action(
                username=username,
                action="navigate",
                target=url,
                outcome="success",
                session_id=session_id,
            )

            return BrowserActionResult(
                action="navigate",
                status=BrowserActionStatus.SUCCESS,
                message=f"Navigated to {final_url}",
                url=final_url,
                duration_ms=duration_ms,
            )
        except BrowserTimeoutError:
            duration_ms = int((time.time() - start) * 1000)
            self._log_action(
                username=username,
                action="navigate",
                target=url,
                outcome="timeout",
                session_id=session_id,
            )
            return BrowserActionResult(
                action="navigate",
                status=BrowserActionStatus.TIMEOUT,
                message=f"Navigation to {url} timed out after "
                f"{self.action_timeout}s.",
                url=url,
                duration_ms=duration_ms,
            )
        except Exception as exc:
            duration_ms = int((time.time() - start) * 1000)
            self._log_action(
                username=username,
                action="navigate",
                target=url,
                outcome=f"failed: {str(exc)[:200]}",
                session_id=session_id,
            )
            return BrowserActionResult(
                action="navigate",
                status=BrowserActionStatus.FAILED,
                message=f"Navigation failed: {str(exc)[:200]}",
                url=url,
                duration_ms=duration_ms,
            )

    async def click(
        self, selector: str, username: str, session_id: Optional[str] = None
    ) -> BrowserActionResult:
        """
        Click an element by CSS selector.

        Requirement 8.1: click element action.
        Requirement 8.7: 30-second timeout.
        """
        self.check_enabled()
        self._check_forbidden_operation("click", selector)
        start = time.time()

        try:
            await self._ensure_browser()

            async def _do_click():
                await self._page.click(selector)

            await self._execute_with_timeout(_do_click, "click")
            duration_ms = int((time.time() - start) * 1000)

            self._log_action(
                username=username,
                action="click",
                target=selector,
                outcome="success",
                session_id=session_id,
            )

            return BrowserActionResult(
                action="click",
                status=BrowserActionStatus.SUCCESS,
                message=f"Clicked element: {selector}",
                url=self._page.url if self._page else None,
                duration_ms=duration_ms,
            )
        except BrowserTimeoutError:
            duration_ms = int((time.time() - start) * 1000)
            self._log_action(
                username=username,
                action="click",
                target=selector,
                outcome="timeout",
                session_id=session_id,
            )
            return BrowserActionResult(
                action="click",
                status=BrowserActionStatus.TIMEOUT,
                message=f"Click on '{selector}' timed out after "
                f"{self.action_timeout}s.",
                duration_ms=duration_ms,
            )
        except Exception as exc:
            duration_ms = int((time.time() - start) * 1000)
            self._log_action(
                username=username,
                action="click",
                target=selector,
                outcome=f"failed: {str(exc)[:200]}",
                session_id=session_id,
            )
            return BrowserActionResult(
                action="click",
                status=BrowserActionStatus.FAILED,
                message=f"Click failed: {str(exc)[:200]}",
                duration_ms=duration_ms,
            )

    async def type_text(
        self,
        selector: str,
        text: str,
        username: str,
        session_id: Optional[str] = None,
        credentials_provided: bool = False,
    ) -> BrowserActionResult:
        """
        Type text into an element by CSS selector.

        Requirement 8.1: type text action.
        Requirement 8.9: use only user-provided credentials for login.
        """
        self.check_enabled()
        self._check_forbidden_operation(
            "type", selector, allow_credential_input=credentials_provided
        )
        start = time.time()

        # For password fields, only allow user-provided credentials
        is_password_field = "password" in selector.lower() or "pass" in selector.lower()
        if is_password_field and not credentials_provided:
            self._log_action(
                username=username,
                action="type",
                target=selector,
                outcome="blocked: credentials not user-provided",
                session_id=session_id,
            )
            return BrowserActionResult(
                action="type",
                status=BrowserActionStatus.BLOCKED,
                message="Password fields require user-provided credentials. "
                "Cannot use stored or generated passwords.",
                duration_ms=int((time.time() - start) * 1000),
            )

        try:
            await self._ensure_browser()

            async def _do_type():
                await self._page.fill(selector, text)

            await self._execute_with_timeout(_do_type, "type")
            duration_ms = int((time.time() - start) * 1000)

            # Don't log the actual text for security
            log_target = f"{selector} (text length: {len(text)})"
            self._log_action(
                username=username,
                action="type",
                target=log_target,
                outcome="success",
                session_id=session_id,
            )

            return BrowserActionResult(
                action="type",
                status=BrowserActionStatus.SUCCESS,
                message=f"Typed text into: {selector}",
                url=self._page.url if self._page else None,
                duration_ms=duration_ms,
            )
        except BrowserTimeoutError:
            duration_ms = int((time.time() - start) * 1000)
            self._log_action(
                username=username,
                action="type",
                target=selector,
                outcome="timeout",
                session_id=session_id,
            )
            return BrowserActionResult(
                action="type",
                status=BrowserActionStatus.TIMEOUT,
                message=f"Type into '{selector}' timed out after "
                f"{self.action_timeout}s.",
                duration_ms=duration_ms,
            )
        except Exception as exc:
            duration_ms = int((time.time() - start) * 1000)
            self._log_action(
                username=username,
                action="type",
                target=selector,
                outcome=f"failed: {str(exc)[:200]}",
                session_id=session_id,
            )
            return BrowserActionResult(
                action="type",
                status=BrowserActionStatus.FAILED,
                message=f"Type failed: {str(exc)[:200]}",
                duration_ms=duration_ms,
            )

    async def submit_form(
        self, selector: str, username: str, session_id: Optional[str] = None
    ) -> BrowserActionResult:
        """
        Submit a form by CSS selector.

        Requirement 8.1: submit form action.
        Requirement 8.7: 30-second timeout.
        """
        self.check_enabled()
        self._check_forbidden_operation("submit", selector)
        start = time.time()

        try:
            await self._ensure_browser()

            async def _do_submit():
                # Try pressing Enter on the form element or clicking submit
                element = await self._page.query_selector(selector)
                if element:
                    tag = await element.evaluate("el => el.tagName.toLowerCase()")
                    if tag == "form":
                        # Submit the form directly
                        await element.evaluate("form => form.submit()")
                    else:
                        # Click the element (likely a submit button)
                        await element.click()
                else:
                    raise ValueError(f"Element not found: {selector}")

            await self._execute_with_timeout(_do_submit, "submit")
            duration_ms = int((time.time() - start) * 1000)

            self._log_action(
                username=username,
                action="submit",
                target=selector,
                outcome="success",
                session_id=session_id,
            )

            return BrowserActionResult(
                action="submit",
                status=BrowserActionStatus.SUCCESS,
                message=f"Form submitted: {selector}",
                url=self._page.url if self._page else None,
                duration_ms=duration_ms,
            )
        except BrowserTimeoutError:
            duration_ms = int((time.time() - start) * 1000)
            self._log_action(
                username=username,
                action="submit",
                target=selector,
                outcome="timeout",
                session_id=session_id,
            )
            return BrowserActionResult(
                action="submit",
                status=BrowserActionStatus.TIMEOUT,
                message=f"Submit '{selector}' timed out after "
                f"{self.action_timeout}s.",
                duration_ms=duration_ms,
            )
        except Exception as exc:
            duration_ms = int((time.time() - start) * 1000)
            self._log_action(
                username=username,
                action="submit",
                target=selector,
                outcome=f"failed: {str(exc)[:200]}",
                session_id=session_id,
            )
            return BrowserActionResult(
                action="submit",
                status=BrowserActionStatus.FAILED,
                message=f"Submit failed: {str(exc)[:200]}",
                duration_ms=duration_ms,
            )

    async def extract(
        self, username: str, session_id: Optional[str] = None, selector: Optional[str] = None
    ) -> BrowserActionResult:
        """
        Extract page content (text or specific element content).

        Requirement 8.1: extract page content action.
        Requirement 8.7: 30-second timeout.
        Requirement 8.8: refuse password reading.
        """
        self.check_enabled()
        if selector:
            self._check_forbidden_operation("extract", selector)
        start = time.time()

        try:
            await self._ensure_browser()

            async def _do_extract():
                if selector:
                    element = await self._page.query_selector(selector)
                    if element:
                        return await element.inner_text()
                    else:
                        raise ValueError(f"Element not found: {selector}")
                else:
                    return await self._page.inner_text("body")

            content = await self._execute_with_timeout(_do_extract, "extract")
            duration_ms = int((time.time() - start) * 1000)

            # Truncate content to reasonable size
            if content and len(content) > 10000:
                content = content[:10000] + "\n... (truncated)"

            target = selector or self._page.url
            self._log_action(
                username=username,
                action="extract",
                target=target,
                outcome=f"success (chars: {len(content) if content else 0})",
                session_id=session_id,
            )

            return BrowserActionResult(
                action="extract",
                status=BrowserActionStatus.SUCCESS,
                message="Content extracted successfully.",
                data={"content": content, "length": len(content) if content else 0},
                url=self._page.url if self._page else None,
                duration_ms=duration_ms,
            )
        except BrowserTimeoutError:
            duration_ms = int((time.time() - start) * 1000)
            self._log_action(
                username=username,
                action="extract",
                target=selector or "page",
                outcome="timeout",
                session_id=session_id,
            )
            return BrowserActionResult(
                action="extract",
                status=BrowserActionStatus.TIMEOUT,
                message=f"Extract timed out after {self.action_timeout}s.",
                duration_ms=duration_ms,
            )
        except Exception as exc:
            duration_ms = int((time.time() - start) * 1000)
            self._log_action(
                username=username,
                action="extract",
                target=selector or "page",
                outcome=f"failed: {str(exc)[:200]}",
                session_id=session_id,
            )
            return BrowserActionResult(
                action="extract",
                status=BrowserActionStatus.FAILED,
                message=f"Extract failed: {str(exc)[:200]}",
                duration_ms=duration_ms,
            )

    async def screenshot(
        self, username: str, session_id: Optional[str] = None, full_page: bool = False
    ) -> BrowserActionResult:
        """
        Take a screenshot of the current page.

        Requirement 8.1: take screenshot action.
        Requirement 8.7: 30-second timeout.
        """
        self.check_enabled()
        start = time.time()

        try:
            await self._ensure_browser()

            async def _do_screenshot():
                return await self._page.screenshot(full_page=full_page)

            screenshot_bytes = await self._execute_with_timeout(
                _do_screenshot, "screenshot"
            )
            duration_ms = int((time.time() - start) * 1000)

            # Encode as base64 for transport
            screenshot_b64 = base64.b64encode(screenshot_bytes).decode("utf-8")

            current_url = self._page.url if self._page else "unknown"
            self._log_action(
                username=username,
                action="screenshot",
                target=current_url,
                outcome=f"success (size: {len(screenshot_bytes)} bytes)",
                session_id=session_id,
            )

            return BrowserActionResult(
                action="screenshot",
                status=BrowserActionStatus.SUCCESS,
                message="Screenshot captured.",
                data={
                    "image_base64": screenshot_b64,
                    "size_bytes": len(screenshot_bytes),
                    "full_page": full_page,
                },
                url=current_url,
                duration_ms=duration_ms,
            )
        except BrowserTimeoutError:
            duration_ms = int((time.time() - start) * 1000)
            self._log_action(
                username=username,
                action="screenshot",
                target="page",
                outcome="timeout",
                session_id=session_id,
            )
            return BrowserActionResult(
                action="screenshot",
                status=BrowserActionStatus.TIMEOUT,
                message=f"Screenshot timed out after {self.action_timeout}s.",
                duration_ms=duration_ms,
            )
        except Exception as exc:
            duration_ms = int((time.time() - start) * 1000)
            self._log_action(
                username=username,
                action="screenshot",
                target="page",
                outcome=f"failed: {str(exc)[:200]}",
                session_id=session_id,
            )
            return BrowserActionResult(
                action="screenshot",
                status=BrowserActionStatus.FAILED,
                message=f"Screenshot failed: {str(exc)[:200]}",
                duration_ms=duration_ms,
            )

    async def summarize(
        self, username: str, session_id: Optional[str] = None
    ) -> BrowserActionResult:
        """
        Summarize the current page content.

        Requirement 8.1: summarize page action.
        Extracts text and returns a condensed version.
        """
        self.check_enabled()
        start = time.time()

        try:
            await self._ensure_browser()

            async def _do_summarize():
                # Extract page text
                text = await self._page.inner_text("body")
                # Truncate to a reasonable summary length
                if text and len(text) > 5000:
                    text = text[:5000]
                return text

            page_text = await self._execute_with_timeout(
                _do_summarize, "summarize"
            )
            duration_ms = int((time.time() - start) * 1000)

            # Get page title and URL for context
            title = await self._page.title() if self._page else ""
            current_url = self._page.url if self._page else "unknown"

            summary = (
                f"Page: {title}\nURL: {current_url}\n\n"
                f"Content preview ({len(page_text)} chars):\n{page_text}"
            )

            self._log_action(
                username=username,
                action="summarize",
                target=current_url,
                outcome="success",
                session_id=session_id,
            )

            return BrowserActionResult(
                action="summarize",
                status=BrowserActionStatus.SUCCESS,
                message="Page summarized.",
                data={
                    "title": title,
                    "summary": summary,
                    "content_length": len(page_text) if page_text else 0,
                },
                url=current_url,
                duration_ms=duration_ms,
            )
        except BrowserTimeoutError:
            duration_ms = int((time.time() - start) * 1000)
            self._log_action(
                username=username,
                action="summarize",
                target="page",
                outcome="timeout",
                session_id=session_id,
            )
            return BrowserActionResult(
                action="summarize",
                status=BrowserActionStatus.TIMEOUT,
                message=f"Summarize timed out after {self.action_timeout}s.",
                duration_ms=duration_ms,
            )
        except Exception as exc:
            duration_ms = int((time.time() - start) * 1000)
            self._log_action(
                username=username,
                action="summarize",
                target="page",
                outcome=f"failed: {str(exc)[:200]}",
                session_id=session_id,
            )
            return BrowserActionResult(
                action="summarize",
                status=BrowserActionStatus.FAILED,
                message=f"Summarize failed: {str(exc)[:200]}",
                duration_ms=duration_ms,
            )

    async def close(
        self, username: str, session_id: Optional[str] = None
    ) -> BrowserActionResult:
        """
        Close the browser instance.

        Requirement 8.1: close browser action.
        """
        self.check_enabled()
        start = time.time()

        try:
            if self._page and not self._page.is_closed():
                await self._page.close()
            if self._context:
                await self._context.close()
            if self._browser:
                await self._browser.close()

            self._page = None
            self._context = None
            self._browser = None

            duration_ms = int((time.time() - start) * 1000)

            self._log_action(
                username=username,
                action="close",
                target="browser",
                outcome="success",
                session_id=session_id,
            )

            return BrowserActionResult(
                action="close",
                status=BrowserActionStatus.SUCCESS,
                message="Browser closed.",
                duration_ms=duration_ms,
            )
        except Exception as exc:
            duration_ms = int((time.time() - start) * 1000)
            # Force cleanup
            self._page = None
            self._context = None
            self._browser = None

            self._log_action(
                username=username,
                action="close",
                target="browser",
                outcome=f"failed: {str(exc)[:200]}",
                session_id=session_id,
            )

            return BrowserActionResult(
                action="close",
                status=BrowserActionStatus.FAILED,
                message=f"Close failed (resources freed): {str(exc)[:200]}",
                duration_ms=duration_ms,
            )

    # ------------------------------------------------------------------
    # High-level action dispatcher
    # ------------------------------------------------------------------

    async def execute_action(
        self,
        action: str,
        username: str,
        session_id: Optional[str] = None,
        url: Optional[str] = None,
        selector: Optional[str] = None,
        value: Optional[str] = None,
        credentials_provided: bool = False,
        full_page: bool = False,
    ) -> BrowserActionResult:
        """
        Dispatch a browser action by name.

        Validates enabled state and forbidden operations before dispatching.
        All actions enforce the 30-second timeout.

        Args:
            action: One of open, navigate, click, type, submit, extract,
                    screenshot, summarize, close.
            username: The user performing the action.
            session_id: Optional session ID for audit logging.
            url: URL for navigate action.
            selector: CSS selector for click, type, submit, extract.
            value: Text value for type action.
            credentials_provided: Whether credentials are user-provided.
            full_page: Whether to capture full page screenshot.
        """
        action = action.lower().strip()

        try:
            if action == "open":
                return await self.open_browser(username, session_id)
            elif action == "navigate":
                if not url:
                    return BrowserActionResult(
                        action="navigate",
                        status=BrowserActionStatus.FAILED,
                        message="URL is required for navigate action.",
                    )
                return await self.navigate(url, username, session_id)
            elif action == "click":
                if not selector:
                    return BrowserActionResult(
                        action="click",
                        status=BrowserActionStatus.FAILED,
                        message="Selector is required for click action.",
                    )
                return await self.click(selector, username, session_id)
            elif action == "type":
                if not selector or value is None:
                    return BrowserActionResult(
                        action="type",
                        status=BrowserActionStatus.FAILED,
                        message="Selector and value are required for type action.",
                    )
                return await self.type_text(
                    selector, value, username, session_id, credentials_provided
                )
            elif action == "submit":
                if not selector:
                    return BrowserActionResult(
                        action="submit",
                        status=BrowserActionStatus.FAILED,
                        message="Selector is required for submit action.",
                    )
                return await self.submit_form(selector, username, session_id)
            elif action == "extract":
                return await self.extract(username, session_id, selector)
            elif action == "screenshot":
                return await self.screenshot(username, session_id, full_page)
            elif action == "summarize":
                return await self.summarize(username, session_id)
            elif action == "close":
                return await self.close(username, session_id)
            else:
                return BrowserActionResult(
                    action=action,
                    status=BrowserActionStatus.FAILED,
                    message=f"Unknown action: {action}. "
                    f"Supported: open, navigate, click, type, submit, "
                    f"extract, screenshot, summarize, close.",
                )
        except Exception as exc:
            logger.exception("Browser action %s encountered an error", action)
            return BrowserActionResult(
                action=action,
                status=BrowserActionStatus.FAILED,
                message=f"Browser execution failed: {str(exc)}",
            )
