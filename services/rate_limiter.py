"""Rate Limiter — per-user request frequency enforcement.

Supports Redis backend with safe in-memory fallback when Redis is unavailable.
Never crashes if Redis is down. Audit logging hook for violations.

Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6
"""

from __future__ import annotations

import logging
import os
import time
import threading
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger("ampai.rate_limiter")

# Default limits
DEFAULT_PER_MINUTE = 10
DEFAULT_PER_DAY = 100


@dataclass
class RateLimitResult:
    """Result of a rate limit check."""

    allowed: bool
    reason: Optional[str] = None
    remaining_minute: int = 0
    remaining_day: int = 0
    retry_after_seconds: int = 0


class _InMemoryBackend:
    """Thread-safe in-memory rate limit counter backend."""

    def __init__(self):
        self._lock = threading.Lock()
        # {key: [(timestamp, count)]}
        self._minute_counters: Dict[str, list] = defaultdict(list)
        self._day_counters: Dict[str, int] = defaultdict(int)
        self._day_keys: Dict[str, str] = {}  # key -> date string

    def increment_and_check(
        self, username: str, endpoint: str, per_minute: int, per_day: int
    ) -> Tuple[int, int]:
        """Increment counters and return (minute_count, day_count)."""
        now = time.time()
        minute_key = f"{username}:{endpoint}:minute"
        day_key = f"{username}:{endpoint}:day"
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        with self._lock:
            # Clean expired minute entries (older than 60s)
            entries = self._minute_counters[minute_key]
            entries[:] = [ts for ts in entries if now - ts < 60]
            entries.append(now)
            minute_count = len(entries)

            # Day counter - reset if new day
            stored_day = self._day_keys.get(day_key)
            if stored_day != today:
                self._day_counters[day_key] = 0
                self._day_keys[day_key] = today
            self._day_counters[day_key] += 1
            day_count = self._day_counters[day_key]

        return minute_count, day_count

    def get_counts(self, username: str, endpoint: str) -> Tuple[int, int]:
        """Get current counts without incrementing."""
        now = time.time()
        minute_key = f"{username}:{endpoint}:minute"
        day_key = f"{username}:{endpoint}:day"
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        with self._lock:
            entries = self._minute_counters.get(minute_key, [])
            minute_count = len([ts for ts in entries if now - ts < 60])

            stored_day = self._day_keys.get(day_key)
            day_count = self._day_counters.get(day_key, 0) if stored_day == today else 0

        return minute_count, day_count


class _RedisBackend:
    """Redis-backed rate limit counter backend."""

    def __init__(self, redis_client):
        self._redis = redis_client

    def increment_and_check(
        self, username: str, endpoint: str, per_minute: int, per_day: int
    ) -> Tuple[int, int]:
        """Increment counters in Redis and return (minute_count, day_count)."""
        now_ts = int(time.time())
        window_id = now_ts // 60  # 1-minute window
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        minute_key = f"ratelimit:{username}:{endpoint}:minute:{window_id}"
        day_key = f"ratelimit:{username}:{endpoint}:day:{today}"

        pipe = self._redis.pipeline()
        pipe.incr(minute_key)
        pipe.expire(minute_key, 120)  # 2 minutes TTL for safety
        pipe.incr(day_key)
        pipe.expire(day_key, 90000)  # ~25 hours TTL for safety
        results = pipe.execute()

        minute_count = int(results[0])
        day_count = int(results[2])

        return minute_count, day_count

    def get_counts(self, username: str, endpoint: str) -> Tuple[int, int]:
        """Get current counts from Redis without incrementing."""
        now_ts = int(time.time())
        window_id = now_ts // 60
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        minute_key = f"ratelimit:{username}:{endpoint}:minute:{window_id}"
        day_key = f"ratelimit:{username}:{endpoint}:day:{today}"

        pipe = self._redis.pipeline()
        pipe.get(minute_key)
        pipe.get(day_key)
        results = pipe.execute()

        minute_count = int(results[0] or 0)
        day_count = int(results[1] or 0)

        return minute_count, day_count


class RateLimiter:
    """Per-user rate limiter with Redis/in-memory fallback.

    Never crashes if Redis is down. Falls back to in-memory counters.
    """

    def __init__(
        self,
        redis_url: Optional[str] = None,
        audit_logger=None,
        per_minute: int = DEFAULT_PER_MINUTE,
        per_day: int = DEFAULT_PER_DAY,
    ):
        self._per_minute = per_minute
        self._per_day = per_day
        self._audit_logger = audit_logger
        self._fallback = _InMemoryBackend()
        self._redis_backend: Optional[_RedisBackend] = None
        self._using_redis = False

        # Try to connect to Redis
        url = redis_url or os.getenv("REDIS_URL", "")
        if url:
            try:
                import redis

                client = redis.from_url(url, decode_responses=True, socket_timeout=2)
                client.ping()
                self._redis_backend = _RedisBackend(client)
                self._using_redis = True
                logger.info("RateLimiter using Redis backend")
            except Exception as exc:
                logger.warning(
                    "RateLimiter Redis unavailable, using in-memory fallback: %s", exc
                )

        if not self._using_redis:
            logger.info("RateLimiter using in-memory backend")

    @property
    def backend_type(self) -> str:
        """Return the active backend type."""
        return "redis" if self._using_redis else "memory"

    def check_rate_limit(self, username: str, endpoint: str = "web-search") -> RateLimitResult:
        """Check if user is within rate limits. Increments counters.

        Returns RateLimitResult with allowed/denied status.
        Never raises exceptions — falls back to in-memory on Redis failure.
        """
        try:
            if self._using_redis and self._redis_backend:
                try:
                    minute_count, day_count = self._redis_backend.increment_and_check(
                        username, endpoint, self._per_minute, self._per_day
                    )
                except Exception as exc:
                    logger.warning("Redis rate limit check failed, using fallback: %s", exc)
                    minute_count, day_count = self._fallback.increment_and_check(
                        username, endpoint, self._per_minute, self._per_day
                    )
            else:
                minute_count, day_count = self._fallback.increment_and_check(
                    username, endpoint, self._per_minute, self._per_day
                )

            # Check per-minute limit
            if minute_count > self._per_minute:
                result = RateLimitResult(
                    allowed=False,
                    reason=f"Rate limit exceeded: {self._per_minute} requests per minute",
                    remaining_minute=0,
                    remaining_day=max(0, self._per_day - day_count),
                    retry_after_seconds=60 - (int(time.time()) % 60),
                )
                self._log_violation(username, endpoint, "per_minute")
                return result

            # Check per-day limit
            if day_count > self._per_day:
                result = RateLimitResult(
                    allowed=False,
                    reason=f"Rate limit exceeded: {self._per_day} requests per day",
                    remaining_minute=max(0, self._per_minute - minute_count),
                    remaining_day=0,
                    retry_after_seconds=self._seconds_until_midnight(),
                )
                self._log_violation(username, endpoint, "per_day")
                return result

            return RateLimitResult(
                allowed=True,
                remaining_minute=max(0, self._per_minute - minute_count),
                remaining_day=max(0, self._per_day - day_count),
            )

        except Exception as exc:
            # Never crash — allow the request on unexpected errors
            logger.error("RateLimiter unexpected error (allowing request): %s", exc)
            return RateLimitResult(
                allowed=True,
                remaining_minute=self._per_minute,
                remaining_day=self._per_day,
            )

    def _log_violation(self, username: str, endpoint: str, limit_type: str) -> None:
        """Log rate limit violation to audit logger. Never crashes."""
        if not self._audit_logger:
            return
        try:
            self._audit_logger.log(
                username=username,
                action_type="rate_limit_exceeded",
                details={
                    "endpoint": endpoint,
                    "limit_type": limit_type,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
                category="security",
            )
        except Exception as exc:
            logger.error("Failed to log rate limit violation to audit: %s", exc)

    @staticmethod
    def _seconds_until_midnight() -> int:
        """Seconds remaining until UTC midnight."""
        now = datetime.now(timezone.utc)
        seconds_today = now.hour * 3600 + now.minute * 60 + now.second
        return 86400 - seconds_today
