"""Simple Redis-based rate limiter.

Uses sliding window algorithm with Redis sorted sets.
Provides per-key rate limiting for API endpoints.
"""
from __future__ import annotations

import logging
import time

import redis.asyncio as aioredis

from app.settings import settings

logger = logging.getLogger(__name__)


class RateLimiter:
    """Redis-backed sliding window rate limiter."""

    def __init__(self, redis_url: str | None = None) -> None:
        self._redis_url = redis_url or settings.redis_url
        self._redis: aioredis.Redis | None = None

    async def _get_redis(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = aioredis.from_url(
                self._redis_url,
                decode_responses=True,
            )
        return self._redis

    async def is_allowed(
        self,
        key: str,
        limit: int,
        window_seconds: int = 60,
    ) -> tuple[bool, dict[str, int]]:
        """Check if a request is within rate limits.

        Args:
            key: Rate limit key (e.g., "ratelimit:user:1001").
            limit: Maximum requests allowed in the window.
            window_seconds: Sliding window size in seconds.

        Returns:
            Tuple of (allowed, info_dict) where info_dict contains
            remaining, limit, and reset_seconds.
        """
        redis = await self._get_redis()
        now = time.time()
        window_key = f"ratelimit:{key}:{int(now / window_seconds)}"

        try:
            current = await redis.zcard(window_key)
        except Exception as exc:
            logger.warning("Rate limit check failed, allowing", extra={"error": str(exc)})
            return True, {"remaining": limit, "limit": limit, "reset_seconds": window_seconds}

        if current >= limit:
            return False, {
                "remaining": 0,
                "limit": limit,
                "reset_seconds": window_seconds - int(now % window_seconds),
            }

        # Add this request
        await redis.zadd(window_key, {str(now): now})
        await redis.expire(window_key, window_seconds + 1)

        remaining = limit - current - 1
        return True, {
            "remaining": max(0, remaining),
            "limit": limit,
            "reset_seconds": window_seconds - int(now % window_seconds),
        }

    async def close(self) -> None:
        if self._redis:
            await self._redis.aclose()
            self._redis = None


# Global rate limiter instance
_rate_limiter: RateLimiter | None = None


def get_rate_limiter() -> RateLimiter:
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter
