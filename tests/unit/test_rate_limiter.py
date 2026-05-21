"""Unit tests for services/rate_limiter.py.

Validates:
- 10 requests allowed per minute
- 11th request denied
- Separate users have separate counters
- Redis failure falls back safely
"""

import sys
import os
from unittest.mock import MagicMock, patch

import pytest

# Ensure project root is on path
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, _project_root)

# Mock heavy dependencies
sys.modules.setdefault("logging_utils", MagicMock())

# Import directly to avoid services/__init__.py import chain
import importlib.util
_module_path = os.path.join(_project_root, "services", "rate_limiter.py")
_spec = importlib.util.spec_from_file_location("services.rate_limiter", _module_path)
_module = importlib.util.module_from_spec(_spec)
sys.modules["services.rate_limiter"] = _module
_spec.loader.exec_module(_module)

RateLimiter = _module.RateLimiter
RateLimitResult = _module.RateLimitResult


class TestRateLimiterBasic:
    """Basic rate limiting behavior."""

    def test_first_request_allowed(self):
        """First request should always be allowed."""
        limiter = RateLimiter(per_minute=10, per_day=100)
        result = limiter.check_rate_limit("user1", "web-search")
        assert result.allowed is True
        assert result.remaining_minute == 9
        assert result.remaining_day == 99

    def test_ten_requests_allowed(self):
        """10 requests within a minute should all be allowed."""
        limiter = RateLimiter(per_minute=10, per_day=100)
        for i in range(10):
            result = limiter.check_rate_limit("user1", "web-search")
            assert result.allowed is True, f"Request {i+1} should be allowed"

    def test_eleventh_request_denied(self):
        """11th request within a minute should be denied."""
        limiter = RateLimiter(per_minute=10, per_day=100)
        for _ in range(10):
            limiter.check_rate_limit("user1", "web-search")

        result = limiter.check_rate_limit("user1", "web-search")
        assert result.allowed is False
        assert result.reason is not None
        assert "per minute" in result.reason
        assert result.remaining_minute == 0
        assert result.retry_after_seconds > 0

    def test_separate_users_have_separate_counters(self):
        """Different users should have independent rate limits."""
        limiter = RateLimiter(per_minute=10, per_day=100)

        # Exhaust user1's limit
        for _ in range(10):
            limiter.check_rate_limit("user1", "web-search")

        # user1 should be denied
        result_user1 = limiter.check_rate_limit("user1", "web-search")
        assert result_user1.allowed is False

        # user2 should still be allowed
        result_user2 = limiter.check_rate_limit("user2", "web-search")
        assert result_user2.allowed is True

    def test_daily_limit_enforcement(self):
        """Daily limit should be enforced after per-day count exceeded."""
        limiter = RateLimiter(per_minute=200, per_day=5)  # High minute limit, low day limit

        for _ in range(5):
            result = limiter.check_rate_limit("user1", "web-search")
            assert result.allowed is True

        result = limiter.check_rate_limit("user1", "web-search")
        assert result.allowed is False
        assert "per day" in result.reason
        assert result.remaining_day == 0


class TestRateLimiterRedisFallback:
    """Redis failure fallback behavior."""

    def test_redis_unavailable_uses_memory_fallback(self):
        """When Redis connection fails, should fall back to in-memory."""
        # Mock redis to simulate connection failure
        mock_redis_module = MagicMock()
        mock_client = MagicMock()
        mock_client.ping.side_effect = ConnectionError("Connection refused")
        mock_redis_module.from_url.return_value = mock_client

        with patch.dict(sys.modules, {"redis": mock_redis_module}):
            limiter = RateLimiter(redis_url="redis://unreachable:6379/0", per_minute=10, per_day=100)

        assert limiter.backend_type == "memory"

        # Should still work
        result = limiter.check_rate_limit("user1", "web-search")
        assert result.allowed is True

    def test_no_redis_url_uses_memory(self):
        """When no Redis URL provided, should use in-memory backend."""
        with patch.dict(os.environ, {"REDIS_URL": ""}, clear=False):
            limiter = RateLimiter(redis_url=None, per_minute=10, per_day=100)
        assert limiter.backend_type == "memory"

    def test_never_crashes_on_unexpected_error(self):
        """Rate limiter should never crash — allow request on unexpected errors."""
        limiter = RateLimiter(per_minute=10, per_day=100)
        # Corrupt the internal state to force an error
        limiter._fallback = None
        limiter._using_redis = False

        # Should not raise, should allow the request
        result = limiter.check_rate_limit("user1", "web-search")
        assert result.allowed is True


class TestRateLimiterAudit:
    """Audit logging for rate limit violations."""

    def test_violation_logs_to_audit(self):
        """Rate limit violation should attempt audit logging."""
        mock_audit = MagicMock()
        limiter = RateLimiter(per_minute=2, per_day=100, audit_logger=mock_audit)

        # Use up the limit
        limiter.check_rate_limit("user1", "web-search")
        limiter.check_rate_limit("user1", "web-search")

        # This should trigger audit
        limiter.check_rate_limit("user1", "web-search")

        mock_audit.log.assert_called_once()
        call_kwargs = mock_audit.log.call_args[1]
        assert call_kwargs["username"] == "user1"
        assert call_kwargs["action_type"] == "rate_limit_exceeded"
        assert call_kwargs["details"]["limit_type"] == "per_minute"

    def test_audit_failure_does_not_crash(self):
        """Audit logging failure should not crash the rate limiter."""
        mock_audit = MagicMock()
        mock_audit.log.side_effect = Exception("DB connection lost")
        limiter = RateLimiter(per_minute=1, per_day=100, audit_logger=mock_audit)

        limiter.check_rate_limit("user1", "web-search")
        # This should trigger audit which will fail — but not crash
        result = limiter.check_rate_limit("user1", "web-search")
        assert result.allowed is False  # Still correctly denied


class TestRateLimitResult:
    """RateLimitResult dataclass behavior."""

    def test_allowed_result(self):
        result = RateLimitResult(allowed=True, remaining_minute=9, remaining_day=99)
        assert result.allowed is True
        assert result.reason is None
        assert result.retry_after_seconds == 0

    def test_denied_result(self):
        result = RateLimitResult(
            allowed=False,
            reason="Rate limit exceeded: 10 requests per minute",
            remaining_minute=0,
            remaining_day=50,
            retry_after_seconds=30,
        )
        assert result.allowed is False
        assert "per minute" in result.reason
        assert result.retry_after_seconds == 30
