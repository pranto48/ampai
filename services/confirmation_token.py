"""Confirmation Token Service — HMAC-signed stateless tokens for command/action approval.

Generates and validates time-limited tokens bound to specific operations.
Shared by TerminalService and BrowserAutomationService.

Requirements: 6.1, 6.2, 6.3, 6.4, 7.4, 7.5, 7.6
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger("ampai.confirmation_token")

# Token time-to-live in seconds
TOKEN_TTL_SECONDS = 60

# Known unsafe secrets that must be rejected in production
_UNSAFE_SECRETS = {"change-me", "change-me-for-production", "change-this-long-random-secret", ""}


@dataclass
class ValidationResult:
    """Result of token validation."""

    valid: bool
    reason: str = ""
    expired: bool = False
    mismatch_field: Optional[str] = None


@dataclass
class ConfirmationToken:
    """A signed confirmation token binding an operation to a user/session."""

    username: str
    session_id: str
    action_type: str  # "terminal" or browser action type (navigate, click, submit, etc.)
    command_hash: str  # SHA-256 of the command/action string
    working_directory: str = ""  # Terminal only
    shell_type: str = ""  # Terminal only
    target_url: str = ""  # Browser only
    element_selector: str = ""  # Browser only
    created_at: float = 0.0  # Unix timestamp
    signature: str = ""

    def to_dict(self) -> dict:
        """Serialize token to dict for transport."""
        return {
            "username": self.username,
            "session_id": self.session_id,
            "action_type": self.action_type,
            "command_hash": self.command_hash,
            "working_directory": self.working_directory,
            "shell_type": self.shell_type,
            "target_url": self.target_url,
            "element_selector": self.element_selector,
            "created_at": self.created_at,
            "signature": self.signature,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ConfirmationToken":
        """Deserialize token from dict."""
        return cls(
            username=data.get("username", ""),
            session_id=data.get("session_id", ""),
            action_type=data.get("action_type", ""),
            command_hash=data.get("command_hash", ""),
            working_directory=data.get("working_directory", ""),
            shell_type=data.get("shell_type", ""),
            target_url=data.get("target_url", ""),
            element_selector=data.get("element_selector", ""),
            created_at=float(data.get("created_at", 0)),
            signature=data.get("signature", ""),
        )


class ConfirmationTokenService:
    """Generates and validates HMAC-signed confirmation tokens.

    Tokens are stateless — all binding information is in the token itself.
    Validation checks signature integrity, TTL expiry, and field matching.
    """

    TOKEN_TTL_SECONDS = TOKEN_TTL_SECONDS

    def __init__(self, secret: Optional[str] = None):
        """Initialize with signing secret.

        Uses JWT_SECRET or CONFIG_ENCRYPTION_KEY from environment.
        Refuses weak/default secrets in production.
        """
        self._secret = self._resolve_secret(secret)

    @staticmethod
    def _resolve_secret(explicit: Optional[str] = None) -> str:
        """Resolve the signing secret from explicit value or environment."""
        secret = explicit or os.getenv("JWT_SECRET", "") or os.getenv("CONFIG_ENCRYPTION_KEY", "")

        if not secret:
            logger.warning(
                "ConfirmationTokenService: No signing secret configured. "
                "Using fallback. Set JWT_SECRET or CONFIG_ENCRYPTION_KEY."
            )
            secret = "ampai-dev-fallback-secret-not-for-production"

        env = os.getenv("AMPAI_ENV", "development").strip().lower()
        if env in ("production", "prod") and secret in _UNSAFE_SECRETS:
            raise ValueError(
                "ConfirmationTokenService: Refusing to use weak/default secret in production. "
                "Set a strong JWT_SECRET or CONFIG_ENCRYPTION_KEY."
            )

        return secret

    def _compute_signature(self, token: ConfirmationToken) -> str:
        """Compute HMAC-SHA256 signature over all binding fields."""
        payload = "|".join([
            token.username,
            token.session_id,
            token.action_type,
            token.command_hash,
            token.working_directory,
            token.shell_type,
            token.target_url,
            token.element_selector,
            str(token.created_at),
        ])
        return hmac.HMAC(
            self._secret.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    @staticmethod
    def _hash_command(command: str) -> str:
        """Compute SHA-256 hash of a command string."""
        return hashlib.sha256(command.encode("utf-8")).hexdigest()

    # ------------------------------------------------------------------
    # Terminal token methods
    # ------------------------------------------------------------------

    def create_terminal_token(
        self,
        username: str,
        session_id: str,
        command: str,
        working_directory: str = "",
        shell_type: str = "",
    ) -> ConfirmationToken:
        """Create a signed confirmation token for a terminal command.

        Args:
            username: Authenticated user requesting the command.
            session_id: Current session identifier.
            command: The full command string to be executed.
            working_directory: Directory the command will run in.
            shell_type: Shell type (bash, zsh, powershell, cmd).

        Returns:
            A signed ConfirmationToken.
        """
        token = ConfirmationToken(
            username=username,
            session_id=session_id,
            action_type="terminal",
            command_hash=self._hash_command(command),
            working_directory=working_directory,
            shell_type=shell_type,
            created_at=time.time(),
        )
        token.signature = self._compute_signature(token)
        return token

    def validate_terminal_token(
        self,
        token: ConfirmationToken,
        username: str,
        session_id: str,
        command: str,
        working_directory: str = "",
        shell_type: str = "",
    ) -> ValidationResult:
        """Validate a terminal confirmation token.

        Checks:
        1. Signature integrity (HMAC-SHA256)
        2. TTL expiry (60 seconds)
        3. Username match
        4. Session ID match
        5. Command hash match (SHA-256 of command string)
        6. Working directory match
        7. Shell type match

        Returns:
            ValidationResult with valid/invalid status and reason.
        """
        # Check signature
        expected_sig = self._compute_signature(token)
        if not hmac.compare_digest(token.signature, expected_sig):
            return ValidationResult(valid=False, reason="Invalid token signature (tampered)")

        # Check expiry
        age = time.time() - token.created_at
        if age > self.TOKEN_TTL_SECONDS:
            return ValidationResult(
                valid=False,
                reason=f"Token expired ({int(age)}s > {self.TOKEN_TTL_SECONDS}s TTL)",
                expired=True,
            )

        # Check binding fields
        if token.username != username:
            return ValidationResult(valid=False, reason="Username mismatch", mismatch_field="username")

        if token.session_id != session_id:
            return ValidationResult(valid=False, reason="Session ID mismatch", mismatch_field="session_id")

        expected_hash = self._hash_command(command)
        if token.command_hash != expected_hash:
            return ValidationResult(
                valid=False,
                reason="Command hash mismatch (different command)",
                mismatch_field="command_hash",
            )

        if token.working_directory != working_directory:
            return ValidationResult(
                valid=False,
                reason="Working directory mismatch",
                mismatch_field="working_directory",
            )

        if token.shell_type != shell_type:
            return ValidationResult(valid=False, reason="Shell type mismatch", mismatch_field="shell_type")

        return ValidationResult(valid=True, reason="Token is valid")

    # ------------------------------------------------------------------
    # Browser token methods
    # ------------------------------------------------------------------

    def create_browser_token(
        self,
        username: str,
        session_id: str,
        action_type: str,
        target_url: str = "",
        element_selector: str = "",
    ) -> ConfirmationToken:
        """Create a signed confirmation token for a browser action.

        Args:
            username: Authenticated user requesting the action.
            session_id: Current session identifier.
            action_type: Browser action (navigate, click, submit, type, etc.).
            target_url: Target URL for the action.
            element_selector: CSS selector for the target element.

        Returns:
            A signed ConfirmationToken.
        """
        # For browser tokens, the "command" is the action description
        action_desc = f"{action_type}:{target_url}:{element_selector}"
        token = ConfirmationToken(
            username=username,
            session_id=session_id,
            action_type=action_type,
            command_hash=self._hash_command(action_desc),
            target_url=target_url,
            element_selector=element_selector,
            created_at=time.time(),
        )
        token.signature = self._compute_signature(token)
        return token

    def validate_browser_token(
        self,
        token: ConfirmationToken,
        username: str,
        session_id: str,
        action_type: str,
        target_url: str = "",
        element_selector: str = "",
    ) -> ValidationResult:
        """Validate a browser confirmation token.

        Checks:
        1. Signature integrity (HMAC-SHA256)
        2. TTL expiry (60 seconds)
        3. Username match
        4. Session ID match
        5. Action type match
        6. Target URL match
        7. Element selector match

        Returns:
            ValidationResult with valid/invalid status and reason.
        """
        # Check signature
        expected_sig = self._compute_signature(token)
        if not hmac.compare_digest(token.signature, expected_sig):
            return ValidationResult(valid=False, reason="Invalid token signature (tampered)")

        # Check expiry
        age = time.time() - token.created_at
        if age > self.TOKEN_TTL_SECONDS:
            return ValidationResult(
                valid=False,
                reason=f"Token expired ({int(age)}s > {self.TOKEN_TTL_SECONDS}s TTL)",
                expired=True,
            )

        # Check binding fields
        if token.username != username:
            return ValidationResult(valid=False, reason="Username mismatch", mismatch_field="username")

        if token.session_id != session_id:
            return ValidationResult(valid=False, reason="Session ID mismatch", mismatch_field="session_id")

        if token.action_type != action_type:
            return ValidationResult(valid=False, reason="Action type mismatch", mismatch_field="action_type")

        if token.target_url != target_url:
            return ValidationResult(valid=False, reason="Target URL mismatch", mismatch_field="target_url")

        if token.element_selector != element_selector:
            return ValidationResult(
                valid=False, reason="Element selector mismatch", mismatch_field="element_selector"
            )

        return ValidationResult(valid=True, reason="Token is valid")
