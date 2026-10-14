"""Outbox Publisher: reads unpublished events from PostgreSQL and publishes
them to RabbitMQ.

Runs in the API process alongside the HTTP server.  The Worker process
also runs its own publisher for tool/agent events produced during graph
execution.

Pattern:
  1. Every N seconds (or on demand), query outbox_event WHERE published_at IS NULL.
  2. For each event, publish to RabbitMQ.
  3. Mark as published (set published_at).
  4. If publish fails, leave unpublished for the next cycle.

Idempotency: event IDs are UUIDs; re-publishing the same event is safe
because consumers deduplicate by event_id + seq.
"""

from __future__ import annotations

import asyncio
import logging

from app.persistence.engine import get_session_factory
from app.persistence.repositories import OutboxRepository
from app.settings import settings

logger = logging.getLogger(__name__)


class OutboxPublisher:
    """Publishes outbox events to RabbitMQ in a background loop."""

    def __init__(
        self,
        interval_seconds: float = 5.0,
        batch_size: int = 100,
    ) -> None:
        self._interval = interval_seconds
        self._batch_size = batch_size
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start the background publishing loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._publish_loop())
        logger.info("Outbox publisher started", extra={"interval": self._interval})

    async def stop(self) -> None:
        """Stop the background publishing loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("Outbox publisher stopped")

    async def publish_once(self) -> int:
        """Publish a single batch of unpublished events.

        Returns the number of events published.
        """
        from app.infra.messaging import publish_event

        factory = get_session_factory()
        async with factory() as session:
            repo = OutboxRepository(session)
            events = await repo.get_unpublished(limit=self._batch_size)
            if not events:
                return 0

            import pika
            with pika.BlockingConnection(pika.URLParameters(settings.rabbitmq_url)) as conn:
                ch = conn.channel()
                published = 0
                for evt in events:
                    try:
                        payload = evt.payload_json or {}
                        publish_event(
                            ch,
                            event_type=evt.event_type,
                            payload=payload,
                        )
                        await repo.mark_published(evt.id)
                        published += 1
                    except Exception as exc:
                        logger.warning(
                            "Failed to publish outbox event",
                            extra={"event_id": evt.id, "error": str(exc)},
                        )
                        # Increment attempt counter
                        evt.attempt += 1
                        evt.last_error = str(exc)
                        break  # Stop on first failure; retry later

                await session.commit()
                logger.debug("Outbox batch published", extra={"count": published})
                return published

    async def _publish_loop(self) -> None:
        """Background loop that publishes events periodically."""
        while self._running:
            try:
                await asyncio.sleep(self._interval)
                await self.publish_once()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Outbox publisher error", extra={"error": str(exc)})
                await asyncio.sleep(min(self._interval * 2, 60))
