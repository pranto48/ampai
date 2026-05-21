"""
Unit tests for integrations/telegram_api.py TelegramBotService.

Tests cover:
- Rate limiting (8 messages per user per 20-second window)
- Access control (allowed_telegram_user_ids)
- Browser/terminal command refusal
- Session ID prefixing with "tg_"
- Failure notification on processing error
- Webhook/polling mode mutual exclusivity
"""
import time
from unittest.mock import MagicMock, patch

import pytest

import sys
import importlib
sys.path.insert(0, "/Users/arif/Documents/Kiro Project/ampai")

# Remove any mocked versions of integrations.telegram_api from sys.modules
# (other test files may have inserted MagicMock stubs for import isolation)
_modules_to_purge = [k for k in sys.modules if k.startswith("integrations")]
for _mod_key in _modules_to_purge:
    if hasattr(sys.modules[_mod_key], "_mock_name"):
        del sys.modules[_mod_key]

# Force-reload the real module
import integrations.telegram_api
importlib.reload(integrations.telegram_api)

from integrations.telegram_api import (
    RateLimiter,
    TelegramBotConfig,
    TelegramBotService,
    TELEGRAM_GENERIC_FAILURE_TEXT,
    TELEGRAM_RATE_LIMIT_COUNT,
    TELEGRAM_RATE_LIMIT_WINDOW_SECONDS,
)


# =============================================================================
# FIXTURES
# =============================================================================

def _make_update(user_id: int = 123, chat_id: int = 456, text: str = "hello") -> dict:
    """Create a minimal Telegram update object."""
    return {
        "update_id": 1001,
        "message": {
            "from": {"id": user_id},
            "chat": {"id": chat_id},
            "text": text,
        },
    }


def _make_service(
    allowed_ids=None,
    tool_access=False,
    chat_response="Hi there!",
    chat_raises=False,
) -> tuple:
    """Create a TelegramBotService with mocked dependencies."""
    config = TelegramBotConfig(
        bot_token="test-token",
        enabled=True,
        allowed_telegram_user_ids=allowed_ids or [],
        telegram_tool_access_enabled=tool_access,
    )

    chat_handler = MagicMock()
    if chat_raises:
        chat_handler.side_effect = RuntimeError("LLM timeout")
    else:
        chat_handler.return_value = {"response": chat_response}

    audit_logger = MagicMock()
    user_resolver = MagicMock(return_value="arif")
    session_manager = MagicMock()

    service = TelegramBotService(
        config=config,
        chat_handler=chat_handler,
        audit_logger=audit_logger,
        user_resolver=user_resolver,
        session_manager=session_manager,
    )

    return service, chat_handler, audit_logger, user_resolver, session_manager


# =============================================================================
# RATE LIMITER TESTS
# =============================================================================

class TestRateLimiter:
    def test_allows_up_to_max_count(self):
        limiter = RateLimiter(max_count=8, window_seconds=20)
        for _ in range(8):
            assert limiter.is_rate_limited("user1") is False

    def test_blocks_after_max_count(self):
        limiter = RateLimiter(max_count=8, window_seconds=20)
        for _ in range(8):
            limiter.is_rate_limited("user1")
        # 9th message should be rate limited
        assert limiter.is_rate_limited("user1") is True

    def test_separate_users_have_separate_buckets(self):
        limiter = RateLimiter(max_count=8, window_seconds=20)
        for _ in range(8):
            limiter.is_rate_limited("user1")
        # user2 should not be affected
        assert limiter.is_rate_limited("user2") is False

    def test_window_expiry_resets_limit(self):
        limiter = RateLimiter(max_count=2, window_seconds=0.1)
        limiter.is_rate_limited("user1")
        limiter.is_rate_limited("user1")
        assert limiter.is_rate_limited("user1") is True
        # Wait for window to expire
        time.sleep(0.15)
        assert limiter.is_rate_limited("user1") is False

    def test_reset_clears_all_state(self):
        limiter = RateLimiter(max_count=1, window_seconds=20)
        limiter.is_rate_limited("user1")
        assert limiter.is_rate_limited("user1") is True
        limiter.reset()
        assert limiter.is_rate_limited("user1") is False


# =============================================================================
# ACCESS CONTROL TESTS
# =============================================================================

class TestAccessControl:
    def test_allowed_user_passes(self):
        service, chat_handler, audit_logger, _, _ = _make_service(allowed_ids=[123])
        update = _make_update(user_id=123)

        with patch.object(service, "_send_reply"):
            result = service.process_webhook_update(update)

        assert result["status"] == "ok"
        chat_handler.assert_called_once()

    def test_disallowed_user_silently_discarded(self):
        service, chat_handler, audit_logger, _, _ = _make_service(allowed_ids=[999])
        update = _make_update(user_id=123)

        result = service.process_webhook_update(update)

        assert result["status"] == "ok"
        chat_handler.assert_not_called()
        # Audit event should be logged for unauthorized user
        audit_logger.assert_called_with(
            "telegram-123",
            "integration.telegram.unauthorized_user_discarded",
            details="telegram_user_id=123",
        )

    def test_empty_allowlist_allows_all(self):
        """When no allowlist is configured, all users are allowed (backward compat)."""
        service, chat_handler, _, _, _ = _make_service(allowed_ids=[])
        update = _make_update(user_id=12345)

        with patch.object(service, "_send_reply"):
            result = service.process_webhook_update(update)

        assert result["status"] == "ok"
        chat_handler.assert_called_once()


# =============================================================================
# SESSION ID PREFIX TESTS
# =============================================================================

class TestSessionIdPrefix:
    def test_session_id_prefixed_with_tg(self):
        service, chat_handler, _, _, session_manager = _make_service()
        update = _make_update(user_id=123, chat_id=456)

        with patch.object(service, "_send_reply"):
            service.process_webhook_update(update)

        # Session manager should be called with tg_ prefixed session_id
        session_manager.assert_called_once_with("tg_456_123", "arif")

    def test_chat_handler_receives_tg_session_id(self):
        service, chat_handler, _, _, _ = _make_service()
        update = _make_update(user_id=123, chat_id=456)

        with patch.object(service, "_send_reply"):
            service.process_webhook_update(update)

        call_kwargs = chat_handler.call_args
        assert call_kwargs.kwargs["session_id"] == "tg_456_123"


# =============================================================================
# BROWSER/TERMINAL COMMAND REFUSAL TESTS
# =============================================================================

class TestToolAccessRefusal:
    def test_browser_command_refused_without_tool_access(self):
        service, chat_handler, audit_logger, _, _ = _make_service(tool_access=False)
        update = _make_update(text="browser open https://example.com")

        with patch.object(service, "_send_reply") as mock_reply:
            result = service.process_webhook_update(update)

        assert result["status"] == "ok"
        chat_handler.assert_not_called()
        mock_reply.assert_called_once()
        reply_text = mock_reply.call_args[0][1]
        assert "not available" in reply_text

    def test_terminal_command_refused_without_tool_access(self):
        service, chat_handler, audit_logger, _, _ = _make_service(tool_access=False)
        update = _make_update(text="run ls -la /home")

        with patch.object(service, "_send_reply") as mock_reply:
            result = service.process_webhook_update(update)

        assert result["status"] == "ok"
        chat_handler.assert_not_called()
        mock_reply.assert_called_once()

    def test_browser_command_allowed_with_tool_access(self):
        service, chat_handler, _, _, _ = _make_service(tool_access=True)
        update = _make_update(text="browser open https://example.com")

        with patch.object(service, "_send_reply"):
            result = service.process_webhook_update(update)

        assert result["status"] == "ok"
        chat_handler.assert_called_once()

    def test_terminal_command_allowed_with_tool_access(self):
        service, chat_handler, _, _, _ = _make_service(tool_access=True)
        update = _make_update(text="run ls -la /home")

        with patch.object(service, "_send_reply"):
            result = service.process_webhook_update(update)

        assert result["status"] == "ok"
        chat_handler.assert_called_once()

    def test_memory_command_always_allowed(self):
        """Memory commands should pass through regardless of tool access setting."""
        service, chat_handler, _, _, _ = _make_service(tool_access=False)
        update = _make_update(text="remember that I like Python")

        with patch.object(service, "_send_reply"):
            result = service.process_webhook_update(update)

        assert result["status"] == "ok"
        chat_handler.assert_called_once()


# =============================================================================
# FAILURE NOTIFICATION TESTS
# =============================================================================

class TestFailureNotification:
    def test_processing_failure_sends_generic_message(self):
        service, chat_handler, audit_logger, _, _ = _make_service(chat_raises=True)
        update = _make_update(user_id=123, chat_id=456)

        with patch.object(service, "_send_reply") as mock_reply:
            result = service.process_webhook_update(update)

        assert result["status"] == "ok"
        mock_reply.assert_called_once_with(456, TELEGRAM_GENERIC_FAILURE_TEXT)

    def test_processing_failure_logs_audit_event(self):
        service, _, audit_logger, _, _ = _make_service(chat_raises=True)
        update = _make_update(user_id=123, chat_id=456)

        with patch.object(service, "_send_reply"):
            service.process_webhook_update(update)

        # Should log the processing failure
        audit_calls = [call for call in audit_logger.call_args_list
                       if "processing_failure" in str(call)]
        assert len(audit_calls) == 1


# =============================================================================
# DISABLED BOT TESTS
# =============================================================================

class TestDisabledBot:
    def test_disabled_bot_ignores_updates(self):
        service, chat_handler, _, _, _ = _make_service()
        service.config.enabled = False
        update = _make_update()

        result = service.process_webhook_update(update)

        assert result["status"] == "ignored"
        assert result["reason"] == "disabled"
        chat_handler.assert_not_called()


# =============================================================================
# RATE LIMITING INTEGRATION TESTS
# =============================================================================

class TestRateLimitingIntegration:
    def test_ninth_message_discarded(self):
        service, chat_handler, _, _, _ = _make_service()

        with patch.object(service, "_send_reply"):
            for i in range(8):
                update = _make_update(user_id=123, chat_id=456, text=f"msg {i}")
                update["update_id"] = 1000 + i
                service.process_webhook_update(update)

            # 9th message should be discarded
            update = _make_update(user_id=123, chat_id=456, text="msg 8")
            update["update_id"] = 1008
            result = service.process_webhook_update(update)

        assert result["status"] == "ok"
        assert chat_handler.call_count == 8


# =============================================================================
# WEBHOOK/POLLING MODE TESTS
# =============================================================================

class TestModeManagement:
    def test_enable_polling_deregisters_webhook(self):
        service, _, _, _, _ = _make_service()

        with patch("integrations.telegram_api.delete_webhook") as mock_delete:
            with patch.object(service, "_start_polling"):
                service.enable_polling()

            mock_delete.assert_called_once_with("test-token")
            assert service.config.polling_enabled is True

    def test_enable_webhook_stops_polling(self):
        service, _, _, _, _ = _make_service()
        service._polling_active = True

        with patch("integrations.telegram_api.set_webhook", return_value={"ok": True}):
            with patch.object(service, "stop_polling") as mock_stop:
                service.enable_webhook(webhook_url="https://example.com/webhook")

            mock_stop.assert_called_once()
            assert service.config.polling_enabled is False

    def test_enable_polling_without_token_raises(self):
        service, _, _, _, _ = _make_service()
        service.config.bot_token = ""

        with pytest.raises(ValueError, match="Bot token"):
            service.enable_polling()

    def test_enable_webhook_without_token_raises(self):
        service, _, _, _, _ = _make_service()
        service.config.bot_token = ""

        with pytest.raises(ValueError, match="Bot token"):
            service.enable_webhook(webhook_url="https://example.com/webhook")
