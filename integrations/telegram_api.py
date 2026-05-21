"""
Telegram Bot API helpers and full bot lifecycle management.

Low-level API functions raise on failure so callers receive actionable error messages.
The TelegramBotService class manages the full bot lifecycle including:
- Webhook and long-polling modes (mutually exclusive)
- User resolution via telegram_users table
- Access control (allowed_telegram_user_ids)
- Rate limiting (8 messages per user per 20-second window)
- Chat pipeline integration with memory and task commands
- Browser/terminal command refusal unless admin-enabled
- Failure notification and audit logging
"""
from __future__ import annotations

import json
import logging
import re
import ssl
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger("ampai.telegram")

# =============================================================================
# LOW-LEVEL TELEGRAM API HELPERS
# =============================================================================

API_BASE = "https://api.telegram.org"
_DEFAULT_TIMEOUT = 20


def _build_ctx() -> ssl.SSLContext:
    """Return a permissive SSL context that works inside Docker containers."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _do_request(url: str, data: bytes = None, method: str = "GET", timeout: int = _DEFAULT_TIMEOUT) -> dict:
    """
    Make an HTTP request to the Telegram API and return the parsed JSON body.
    Raises urllib.error.HTTPError, urllib.error.URLError, or ValueError on failure.
    """
    req = urllib.request.Request(url, data=data, method=method)
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", None)
        if isinstance(reason, ssl.SSLError) or "CERTIFICATE_VERIFY_FAILED" in str(reason):
            with urllib.request.urlopen(req, timeout=timeout, context=_build_ctx()) as resp:
                return json.loads(resp.read().decode("utf-8"))
        raise
    except ssl.SSLError:
        with urllib.request.urlopen(req, timeout=timeout, context=_build_ctx()) as resp:
            return json.loads(resp.read().decode("utf-8"))


def _read_http_error(exc: urllib.error.HTTPError) -> str:
    try:
        body = (exc.read() or b"").decode("utf-8", errors="ignore")[:600]
        obj = json.loads(body)
        return obj.get("description") or body
    except Exception:
        return getattr(exc, "reason", str(exc))


def get_me(bot_token: str) -> dict:
    """
    Call getMe. Returns the raw Telegram JSON on success.
    Raises HTTPError (bad token → 401) or URLError (network/DNS).
    """
    url = f"{API_BASE}/bot{bot_token}/getMe"
    return _do_request(url)


def set_webhook(bot_token: str, webhook_url: str, secret_token: str = None) -> dict:
    url = f"{API_BASE}/bot{bot_token}/setWebhook"
    payload: dict = {"url": webhook_url}
    if secret_token:
        payload["secret_token"] = secret_token
    return _do_request(url, data=json.dumps(payload).encode(), method="POST")


def delete_webhook(bot_token: str) -> dict:
    url = f"{API_BASE}/bot{bot_token}/deleteWebhook"
    return _do_request(url, data=b"{}", method="POST")


def send_message(bot_token: str, chat_id, text: str) -> dict:
    url = f"{API_BASE}/bot{bot_token}/sendMessage"
    payload = json.dumps({"chat_id": chat_id, "text": str(text)[:4000]}).encode()
    return _do_request(url, data=payload, method="POST")


def get_webhook_info(bot_token: str) -> dict:
    url = f"{API_BASE}/bot{bot_token}/getWebhookInfo"
    return _do_request(url)


def get_updates(bot_token: str, offset: int = 0, timeout: int = 0, allowed_updates=None) -> dict:
    params = {"timeout": timeout, "offset": offset}
    if allowed_updates:
        params["allowed_updates"] = json.dumps(allowed_updates)
    qs = urllib.parse.urlencode(params)
    url = f"{API_BASE}/bot{bot_token}/getUpdates?{qs}"
    return _do_request(url, timeout=timeout + 10)


# =============================================================================
# BOT LIFECYCLE CONSTANTS
# =============================================================================

TELEGRAM_MAX_MESSAGE_CHARS = 4000
TELEGRAM_RATE_LIMIT_COUNT = 8
TELEGRAM_RATE_LIMIT_WINDOW_SECONDS = 20
TELEGRAM_GENERIC_FAILURE_TEXT = (
    "Sorry, something went wrong while processing your message."
)
TELEGRAM_POLL_TIMEOUT_SECONDS = 25
TELEGRAM_POLL_SLEEP_SECONDS = 1.5

# Patterns that indicate browser/terminal commands
_BROWSER_COMMAND_PATTERNS = [
    r"(?i)^(open|navigate|browse|go to|visit)\s+(https?://|www\.)",
    r"(?i)^browser\s+(open|navigate|click|type|submit|extract|screenshot|close)",
    r"(?i)^(take\s+)?screenshot",
    r"(?i)^extract\s+(page|text|tables?)",
]

_TERMINAL_COMMAND_PATTERNS = [
    r"(?i)^(run|execute|exec|shell|terminal|cmd|command)\s+",
    r"(?i)^(ls|cd|mkdir|rm|cat|grep|find|pip|npm|git|docker|python|node)\s",
    r"(?i)^(powershell|bash|sh|zsh)\s",
]


# =============================================================================
# RATE LIMITER
# =============================================================================

class RateLimiter:
    """
    Per-user rate limiter: discards messages beyond max_count per window_seconds.
    Thread-safe.
    """

    def __init__(self, max_count: int = TELEGRAM_RATE_LIMIT_COUNT,
                 window_seconds: float = TELEGRAM_RATE_LIMIT_WINDOW_SECONDS):
        self._max_count = max_count
        self._window_seconds = window_seconds
        self._lock = threading.Lock()
        self._buckets: Dict[str, List[float]] = {}

    def is_rate_limited(self, user_key: str) -> bool:
        """Return True if the user has exceeded the rate limit."""
        now = time.time()
        with self._lock:
            bucket = self._buckets.get(user_key, [])
            # Prune expired timestamps
            bucket = [ts for ts in bucket if now - ts < self._window_seconds]
            if len(bucket) >= self._max_count:
                self._buckets[user_key] = bucket
                return True
            bucket.append(now)
            self._buckets[user_key] = bucket
        return False

    def reset(self) -> None:
        """Clear all rate limit state (useful for testing)."""
        with self._lock:
            self._buckets.clear()


# =============================================================================
# TELEGRAM BOT SERVICE
# =============================================================================

@dataclass
class TelegramBotConfig:
    """Configuration for the Telegram bot service."""
    bot_token: str = ""
    webhook_url: str = ""
    webhook_secret: str = ""
    enabled: bool = False
    polling_enabled: bool = False
    # Allowed Telegram user IDs. Empty list = no users allowed.
    allowed_telegram_user_ids: List[int] = field(default_factory=list)
    # Whether browser/terminal tools are enabled for Telegram
    telegram_tool_access_enabled: bool = False


class TelegramBotService:
    """
    Full Telegram bot lifecycle manager.

    Supports webhook and long-polling modes (mutually exclusive).
    Integrates with the AmpAI chat pipeline, memory system, and audit logger.
    """

    def __init__(
        self,
        config: TelegramBotConfig,
        chat_handler: Optional[Callable] = None,
        audit_logger: Optional[Callable] = None,
        user_resolver: Optional[Callable] = None,
        session_manager: Optional[Callable] = None,
    ):
        """
        Args:
            config: Bot configuration
            chat_handler: Callable(session_id, message, username, **kwargs) -> dict
            audit_logger: Callable(username, action, session_id=None, details=None)
            user_resolver: Callable(telegram_user_id) -> Optional[str] (AmpAI username)
            session_manager: Callable(session_id, username) -> None (ensure session exists)
        """
        self._config = config
        self._chat_handler = chat_handler
        self._audit_logger = audit_logger or self._noop_audit
        self._user_resolver = user_resolver
        self._session_manager = session_manager

        self._rate_limiter = RateLimiter()
        self._polling_active = False
        self._polling_thread: Optional[threading.Thread] = None
        self._polling_stop_event = threading.Event()
        self._poll_offset = 0
        self._poll_offset_lock = threading.Lock()
        self._processed_update_ids: Set[int] = set()
        self._processed_ids_lock = threading.Lock()

    @property
    def config(self) -> TelegramBotConfig:
        return self._config

    @config.setter
    def config(self, value: TelegramBotConfig) -> None:
        self._config = value

    @property
    def is_polling(self) -> bool:
        return self._polling_active

    # ── Mode management ───────────────────────────────────────────────────────

    def enable_webhook(self, webhook_url: str = "", secret_token: str = "") -> dict:
        """
        Enable webhook mode. Stops polling if active.
        Returns the Telegram API response.
        """
        # Stop polling first (only one mode active at a time)
        if self._polling_active:
            self.stop_polling()

        url = webhook_url or self._config.webhook_url
        secret = secret_token or self._config.webhook_secret
        if not self._config.bot_token:
            raise ValueError("Bot token is not configured")
        if not url:
            raise ValueError("Webhook URL is not configured")

        result = set_webhook(self._config.bot_token, url, secret_token=secret or None)
        self._config.webhook_url = url
        self._config.webhook_secret = secret
        self._config.polling_enabled = False
        self._audit_logger("system", "integration.telegram.webhook_enabled",
                           details=f"webhook_url={url}")
        return result

    def enable_polling(self) -> None:
        """
        Enable long-polling mode. Deregisters any active webhook first.
        Only one mode is active at a time.
        """
        if not self._config.bot_token:
            raise ValueError("Bot token is not configured")

        # Deregister webhook (Req 10.1: enabling polling deregisters webhook)
        try:
            delete_webhook(self._config.bot_token)
        except Exception:
            logger.warning("Failed to deregister webhook when enabling polling")

        self._config.polling_enabled = True
        self._start_polling()
        self._audit_logger("system", "integration.telegram.polling_enabled")

    def stop_polling(self) -> None:
        """Stop the long-polling worker thread."""
        self._polling_active = False
        self._config.polling_enabled = False
        self._polling_stop_event.set()
        if self._polling_thread and self._polling_thread.is_alive():
            self._polling_thread.join(timeout=TELEGRAM_POLL_TIMEOUT_SECONDS + 5)
        self._polling_stop_event.clear()
        self._audit_logger("system", "integration.telegram.polling_stopped")

    def disable_webhook(self) -> dict:
        """Deregister the webhook."""
        if not self._config.bot_token:
            raise ValueError("Bot token is not configured")
        result = delete_webhook(self._config.bot_token)
        self._config.webhook_url = ""
        self._audit_logger("system", "integration.telegram.webhook_disabled")
        return result

    # ── Update processing ─────────────────────────────────────────────────────

    def process_webhook_update(self, update: Dict[str, Any]) -> Dict[str, str]:
        """
        Process a single update received via webhook.
        Returns a status dict for the HTTP response.
        """
        if not self._config.enabled:
            return {"status": "ignored", "reason": "disabled"}

        return self._process_update(update)

    def _process_update(self, update: Dict[str, Any]) -> Dict[str, str]:
        """Core update processing logic shared by webhook and polling."""
        fields = self._extract_update_fields(update)
        user_id = fields.get("user_id")
        chat_id = fields.get("chat_id")
        incoming_text = self._sanitize_text(fields.get("text"))

        # Skip non-text or incomplete updates
        if not fields.get("is_text_update") or not user_id or not chat_id or not incoming_text:
            return {"status": "ok"}

        # Req 10.3: Silently discard messages from user IDs not in allowed list
        if not self._is_user_allowed(user_id):
            self._audit_logger(
                f"telegram-{user_id}",
                "integration.telegram.unauthorized_user_discarded",
                details=f"telegram_user_id={user_id}",
            )
            return {"status": "ok"}

        # Req 10.7: Rate limiting - discard beyond 8 per user per 20s window
        user_key = str(user_id)
        if self._rate_limiter.is_rate_limited(user_key):
            logger.debug("Rate limited telegram user %s", user_id)
            return {"status": "ok"}

        # Req 10.2: Resolve Telegram user ID to AmpAI username via telegram_users table
        username = self._resolve_username(user_id)
        if not username:
            # User is in allowed list but has no mapping - use fallback
            username = f"telegram-{user_id}"

        # Req 10.4: session_id prefixed with "tg_"
        session_id = f"tg_{chat_id}_{user_id}"

        # Ensure session ownership
        if self._session_manager:
            try:
                self._session_manager(session_id, username)
            except Exception:
                logger.warning("Failed to ensure session for telegram user %s", user_id)

        # Req 10.6: Refuse browser/terminal commands unless admin enables Telegram tool access
        if self._is_browser_command(incoming_text) or self._is_terminal_command(incoming_text):
            if not self._config.telegram_tool_access_enabled:
                refusal_text = (
                    "Browser and terminal commands are not available through Telegram. "
                    "An admin must explicitly enable Telegram tool access."
                )
                self._send_reply(chat_id, refusal_text)
                self._audit_logger(
                    username,
                    "integration.telegram.tool_access_refused",
                    session_id=session_id,
                    details=f"command={incoming_text[:100]}",
                )
                return {"status": "ok"}

        # Req 10.5: Process through same chat pipeline (memory + task commands)
        try:
            result = self._invoke_chat_pipeline(
                session_id=session_id,
                message=incoming_text,
                username=username,
            )
            response_text = str((result or {}).get("response") or "").strip()
            if response_text:
                self._send_reply(chat_id, response_text)

            self._audit_logger(
                username,
                "integration.telegram.message_processed",
                session_id=session_id,
            )
            return {"status": "ok"}

        except Exception as exc:
            # Req 10.8: On failure, send generic failure notification, log audit event
            logger.exception("Telegram message processing failed for user %s", user_id)
            try:
                self._send_reply(chat_id, TELEGRAM_GENERIC_FAILURE_TEXT)
            except Exception:
                logger.exception("Failed to send failure notification to chat %s", chat_id)

            self._audit_logger(
                username,
                "integration.telegram.processing_failure",
                session_id=session_id,
                details=f"error={str(exc)[:200]}",
            )
            return {"status": "ok"}

    # ── Polling worker ────────────────────────────────────────────────────────

    def _start_polling(self) -> None:
        """Start the background polling thread."""
        if self._polling_active:
            return
        self._polling_active = True
        self._polling_stop_event.clear()
        self._polling_thread = threading.Thread(
            target=self._poll_loop,
            daemon=True,
            name="ampai-telegram-poller",
        )
        self._polling_thread.start()
        logger.info("Telegram polling worker started")

    def _poll_loop(self) -> None:
        """Long-polling loop that fetches updates from Telegram."""
        while self._polling_active and not self._polling_stop_event.is_set():
            try:
                if not self._config.enabled or not self._config.polling_enabled:
                    self._polling_stop_event.wait(timeout=3)
                    continue

                bot_token = self._config.bot_token
                if not bot_token:
                    self._polling_stop_event.wait(timeout=5)
                    continue

                with self._poll_offset_lock:
                    offset = self._poll_offset

                try:
                    payload = get_updates(
                        bot_token,
                        offset=offset,
                        timeout=TELEGRAM_POLL_TIMEOUT_SECONDS,
                        allowed_updates=["message", "edited_message"],
                    )
                except Exception:
                    logger.exception("Telegram getUpdates failed")
                    self._polling_stop_event.wait(timeout=TELEGRAM_POLL_SLEEP_SECONDS)
                    continue

                if not isinstance(payload, dict) or not payload.get("ok"):
                    self._polling_stop_event.wait(timeout=TELEGRAM_POLL_SLEEP_SECONDS)
                    continue

                for update in payload.get("result") or []:
                    update_id = update.get("update_id")
                    if not self._mark_update_processed(update_id):
                        continue
                    if isinstance(update_id, int):
                        with self._poll_offset_lock:
                            self._poll_offset = max(self._poll_offset, update_id + 1)
                    self._process_update(update)

            except Exception:
                logger.exception("Telegram polling iteration failed")
                self._polling_stop_event.wait(timeout=TELEGRAM_POLL_SLEEP_SECONDS)

        logger.info("Telegram polling worker stopped")

    def _mark_update_processed(self, update_id: Any) -> bool:
        """
        Track processed update IDs to avoid duplicate processing.
        Returns True if this is a new update, False if already processed.
        """
        try:
            normalized = int(update_id)
        except (TypeError, ValueError):
            return True
        with self._processed_ids_lock:
            if normalized in self._processed_update_ids:
                return False
            self._processed_update_ids.add(normalized)
            # Prune old IDs to prevent unbounded growth
            if len(self._processed_update_ids) > 2000:
                min_keep = self._poll_offset - 2000
                self._processed_update_ids = {
                    uid for uid in self._processed_update_ids if uid >= min_keep
                }
        return True

    # ── Access control ────────────────────────────────────────────────────────

    def _is_user_allowed(self, telegram_user_id: Any) -> bool:
        """
        Check if the Telegram user ID is in the allowed list.
        Req 10.3: Silently discard messages from user IDs not in allowed_telegram_user_ids.
        If the allowed list is empty, all users are allowed (backward compatibility
        with existing deployments that don't configure an allowlist).
        """
        allowed = self._config.allowed_telegram_user_ids
        if not allowed:
            # No allowlist configured = allow all (backward compat)
            return True
        try:
            uid = int(telegram_user_id)
        except (TypeError, ValueError):
            return False
        return uid in allowed

    def _resolve_username(self, telegram_user_id: Any) -> Optional[str]:
        """
        Resolve Telegram user ID to AmpAI username via telegram_users table.
        Req 10.2.
        """
        if self._user_resolver:
            try:
                return self._user_resolver(telegram_user_id)
            except Exception:
                logger.warning("User resolver failed for telegram_user_id=%s", telegram_user_id)
        return None

    # ── Command detection ─────────────────────────────────────────────────────

    @staticmethod
    def _is_browser_command(text: str) -> bool:
        """Detect if the message is a browser automation command."""
        for pattern in _BROWSER_COMMAND_PATTERNS:
            if re.search(pattern, text):
                return True
        return False

    @staticmethod
    def _is_terminal_command(text: str) -> bool:
        """Detect if the message is a terminal/shell command."""
        for pattern in _TERMINAL_COMMAND_PATTERNS:
            if re.search(pattern, text):
                return True
        return False

    # ── Chat pipeline integration ─────────────────────────────────────────────

    def _invoke_chat_pipeline(self, session_id: str, message: str, username: str) -> dict:
        """
        Route the message through the same chat pipeline used by desktop/web.
        Req 10.5: Supports memory commands and task commands.
        """
        if not self._chat_handler:
            raise RuntimeError("Chat handler not configured for Telegram bot service")

        return self._chat_handler(
            session_id=session_id,
            message=message,
            username=username,
            model_type=None,  # Use default model
            memory_mode="indexed",
            memory_top_k=5,
            recency_bias=0.6,
            use_web_search=False,
            enable_browser_tools=self._config.telegram_tool_access_enabled,
            enable_terminal_tools=self._config.telegram_tool_access_enabled,
        )

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _send_reply(self, chat_id: Any, text: str) -> None:
        """Send a reply message to the Telegram chat."""
        if not self._config.bot_token or not chat_id or not text:
            return
        try:
            send_message(self._config.bot_token, chat_id, text)
        except Exception:
            logger.exception("Failed to send Telegram message to chat_id=%s", chat_id)
            raise

    @staticmethod
    def _extract_update_fields(update: Dict[str, Any]) -> Dict[str, Any]:
        """Extract relevant fields from a Telegram update object."""
        message_obj = update.get("message") or update.get("edited_message") or {}
        from_obj = message_obj.get("from") or {}
        chat_obj = message_obj.get("chat") or {}
        text = (message_obj.get("text") or "").strip()
        return {
            "user_id": from_obj.get("id"),
            "chat_id": chat_obj.get("id"),
            "text": text,
            "is_text_update": bool(text),
        }

    @staticmethod
    def _sanitize_text(value: Any) -> str:
        """Sanitize incoming text: strip control chars, enforce max length."""
        text = str(value or "")
        text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", " ", text).strip()
        if len(text) > TELEGRAM_MAX_MESSAGE_CHARS:
            text = text[:TELEGRAM_MAX_MESSAGE_CHARS]
        return text

    @staticmethod
    def _noop_audit(*args, **kwargs) -> None:
        """No-op audit logger for when no audit function is provided."""
        pass
