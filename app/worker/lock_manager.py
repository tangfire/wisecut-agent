"""Redis-based distributed lock for Conversation-level mutual exclusion.

Only one Worker may hold the lock for a given conversation_id at a time.
The lock carries a lease TTL and a heartbeat mechanism to extend the lease
while the Worker is actively processing.

Usage:
    lock = await ConversationLock.acquire(redis, conversation_id, run_id)
    if lock is None:
        return  # another worker holds the lock
    try:
        await lock.heartbeat()  # extend TTL periodically
        # ... process run ...
    finally:
        await lock.release()
"""

from __future__ import annotations

import asyncio
import json
import logging
import time

import redis.asyncio as aioredis

from app.settings import settings

logger = logging.getLogger(__name__)

_LOCK_PREFIX = "maa:lock:conversation:"
_LOCK_TTL = settings.redis_lock_ttl_seconds
_HEARTBEAT_INTERVAL = max(5, _LOCK_TTL // 4)  # heartbeat at 1/4 of TTL


class ConversationLock:
    """Represents an acquired conversation lock."""

    def __init__(
        self,
        redis_client: aioredis.Redis,
        conversation_id: str,
        run_id: str,
        ttl: int = _LOCK_TTL,
    ) -> None:
        self._redis = redis_client
        self._conversation_id = conversation_id
        self._run_id = run_id
        self._ttl = ttl
        self._key = f"{_LOCK_PREFIX}{conversation_id}"
        self._heartbeat_task: asyncio.Task | None = None
        self._released = False

    @property
    def key(self) -> str:
        return self._key

    @property
    def run_id(self) -> str:
        return self._run_id

    async def heartbeat(self) -> None:
        """Extend the lock TTL. Safe to call repeatedly."""
        if self._released:
            return
        data = json.dumps({"run_id": self._run_id, "ts": time.time()})
        await self._redis.expire(self._key, self._ttl)

    async def release(self) -> None:
        """Release the lock."""
        self._released = True
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
            self._heartbeat_task = None
        # Only release if we still hold it
        current = await self._redis.get(self._key)
        if current is not None:
            try:
                data = json.loads(current)
                if data.get("run_id") == self._run_id:
                    await self._redis.delete(self._key)
            except (json.JSONDecodeError, KeyError):
                await self._redis.delete(self._key)
        logger.debug(
            "Lock released",
            extra={"conversation_id": self._conversation_id, "run_id": self._run_id},
        )

    async def start_heartbeat(self) -> None:
        """Start background heartbeat task."""
        if self._heartbeat_task:
            return

        async def _beat() -> None:
            while not self._released:
                await asyncio.sleep(_HEARTBEAT_INTERVAL)
                await self.heartbeat()

        self._heartbeat_task = asyncio.create_task(_beat())

    @staticmethod
    async def acquire(
        redis_client: aioredis.Redis,
        conversation_id: str,
        run_id: str,
        ttl: int = _LOCK_TTL,
    ) -> ConversationLock | None:
        """Try to acquire the conversation lock.

        Returns a ConversationLock on success, or None if another worker
        already holds the lock.
        """
        key = f"{_LOCK_PREFIX}{conversation_id}"
        data = json.dumps({"run_id": run_id, "ts": time.time()})
        # SET NX EX: only set if not exists, with TTL
        acquired = await redis_client.set(key, data, nx=True, ex=ttl)
        if acquired:
            lock = ConversationLock(redis_client, conversation_id, run_id, ttl)
            logger.info(
                "Lock acquired",
                extra={"conversation_id": conversation_id, "run_id": run_id},
            )
            return lock
        # Check if the holder is still alive (stale lock detection)
        current = await redis_client.get(key)
        if current is not None:
            try:
                holder = json.loads(current)
                logger.warning(
                    "Lock held by another run",
                    extra={
                        "conversation_id": conversation_id,
                        "holder_run_id": holder.get("run_id"),
                        "requested_run_id": run_id,
                    },
                )
            except json.JSONDecodeError:
                pass
        return None
