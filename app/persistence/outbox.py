"""Outbox publisher for reliable event delivery.

The Outbox pattern ensures events are published exactly once:
1. Business operation + Event row + Outbox row are written in one DB transaction.
2. A background worker picks up unpublished outbox rows and publishes them.
3. Failed publishes are retried up to a max attempts, then moved to DLQ.

Per plan.md section 5.4:
  - Events are written to DB first, then published via Outbox.
  - RabbitMQ is the transport for outbox events.
  - Duplicate publication is prevented by command_id/run_id idempotency.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Coroutine
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.models import OutboxEvent
from app.persistence.repositories import OutboxRepository
from app.protocol.sse import encode_sse_event

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Outbox Publisher
# ---------------------------------------------------------------------------

class OutboxPublisher:
    """Publishes outbox events to RabbitMQ (or any async transport).

    The publisher is designed to be run as a background task:
        publisher = OutboxPublisher(session_factory, rabbitmq_publish_fn)
        await publisher.run(poll_interval=5.0)
    """

    def __init__(
        self,
        session_factory: Callable[[], AsyncSession],
        publish_fn: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
        max_attempts: int = 5,
        batch_size: int = 50,
    ) -> None:
        self._session_factory = session_factory
        self._publish_fn = publish_fn
        self._max_attempts = max_attempts
        self._batch_size = batch_size
        self._running = False

    async def run(self, poll_interval: float = 5.0) -> None:
        """Run the publisher loop until stopped."""
        self._running = True
        logger.info("Outbox publisher started")
        while self._running:
            try:
                await self._publish_batch()
            except Exception as exc:
                logger.exception(f"Outbox publish batch error: {exc}")
            await asyncio.sleep(poll_interval)
        logger.info("Outbox publisher stopped")

    def stop(self) -> None:
        self._running = False

    async def _publish_batch(self) -> None:
        session = self._session_factory()
        try:
            repo = OutboxRepository(session)
            events = await repo.get_unpublished(limit=self._batch_size)
            for event in events:
                try:
                    await self._publish_fn(event.payload_json)
                    await repo.mark_published(event.id)
                    logger.debug(
                        f"Published outbox event {event.id}",
                        extra={"event_type": event.event_type, "aggregate_id": event.aggregate_id},
                    )
                except Exception as exc:
                    logger.warning(
                        f"Failed to publish outbox event {event.id}: {exc}",
                        extra={"event_type": event.event_type, "attempt": event.attempt},
                    )
                    await repo.mark_failed(event.id, str(exc))
        finally:
            await session.close()

    async def publish_event(
        self,
        session: AsyncSession,
        aggregate_type: str,
        aggregate_id: str,
        event_type: str,
        payload: dict[str, Any],
    ) -> OutboxEvent:
        """Enqueue an event for publishing within an existing transaction."""
        repo = OutboxRepository(session)
        return await repo.enqueue(aggregate_type, aggregate_id, event_type, payload)


# ---------------------------------------------------------------------------
# SSE Event Formatter
# ---------------------------------------------------------------------------

def format_sse_event(event_type: str, payload: dict[str, Any], event_id: str | None = None) -> str:
    """Format an event as an SSE frame matching the Go Client's expectations."""
    seq = payload.get("seq", 0)
    event_id_str = event_id or f"evt-{seq}"
    return encode_sse_event(event_id_str, event_type, payload)
