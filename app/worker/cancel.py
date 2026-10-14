"""Cancel propagation: sets a Redis flag that Workers check before processing
each node/tool.

The cancel flow (plan.md §10.3):
  1. API writes cancel_requested_at to the Run record.
  2. API sets Redis cancel flag: `maa:cancel:{run_id}` = "1" with TTL.
  3. Worker checks the flag before each step.
  4. If set, worker stops graph execution, calls provider cancel (if available),
     emits run.cancelled, and releases the conversation lock.
"""

from __future__ import annotations

import logging

import redis.asyncio as aioredis

from app.settings import settings

logger = logging.getLogger(__name__)

_CANCEL_PREFIX = "maa:cancel:"


class CancelController:
    """Controls cancel flag via Redis."""

    def __init__(self, redis_client: aioredis.Redis) -> None:
        self._redis = redis_client

    async def request_cancel(self, run_id: str) -> None:
        """Set the cancel flag for a run."""
        key = f"{_CANCEL_PREFIX}{run_id}"
        await self._redis.set(key, "1", ex=3600)  # 1h TTL
        logger.info("Cancel flag set", extra={"run_id": run_id})

    async def is_cancelled(self, run_id: str) -> bool:
        """Check if cancel has been requested for this run."""
        key = f"{_CANCEL_PREFIX}{run_id}"
        value = await self._redis.get(key)
        return value is not None

    async def clear_cancel(self, run_id: str) -> None:
        """Clear the cancel flag after handling."""
        key = f"{_CANCEL_PREFIX}{run_id}"
        await self._redis.delete(key)
        logger.debug("Cancel flag cleared", extra={"run_id": run_id})
