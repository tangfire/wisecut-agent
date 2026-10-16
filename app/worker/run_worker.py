"""Main Worker loop: consumes Run commands from RabbitMQ, acquires conversation
locks, and executes graph steps.

Threading model:
  - A dedicated daemon thread runs an asyncio event loop.
  - pika BlockingConnection runs in that same thread (required for thread safety).
  - The pika callback schedules work onto the event loop and blocks on a
    threading.Event until the async handler completes.
  - ack/nack happens in the pika I/O thread after the handler returns, so
    the channel is never accessed from another thread.

WP-06 provides the LangGraph-based RunHandler.  The default handler is a
no-op that marks the run as waiting_interaction.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
import time
from collections.abc import Callable, Coroutine
from typing import Any

import pika
from pika.adapters.blocking_connection import BlockingChannel
from pika.spec import Basic

from app.settings import settings
from app.worker.cancel import CancelController
from app.worker.lock_manager import ConversationLock
from app.worker.run_recovery import scan_and_recover

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------

# Async handler: (run_id, conversation_id, command_type, payload, loop) -> None
RunHandler = Callable[
    [str, str, str, dict[str, Any], asyncio.AbstractEventLoop],
    Coroutine[Any, Any, None],
]

# ---------------------------------------------------------------------------
# Worker
# ---------------------------------------------------------------------------


class RunWorker:
    """Consumes RunCommand messages from RabbitMQ and processes them."""

    def __init__(
        self,
        run_handler: RunHandler | None = None,
        prefetch_count: int = 1,
        enable_outbox: bool = False,
    ) -> None:
        self._handler = run_handler or self._default_handler
        self._prefetch = prefetch_count
        self._enable_outbox = enable_outbox
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._connection: pika.BlockingConnection | None = None
        self._channel: BlockingChannel | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            logger.warning("Worker already running")
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="maa-worker")
        self._thread.start()
        logger.info("Worker thread started")

    def stop(self) -> None:
        self._stop_event.set()
        if self._connection and self._connection.is_open:
            try:
                if self._channel and self._channel.is_open:
                    self._channel.stop_consuming()
            except Exception:
                pass
        if self._thread:
            self._thread.join(timeout=10)
        logger.info("Worker stopped")

    def _run_loop(self) -> None:
        """Worker thread entry point: owns the event loop and pika connection."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        # Initialize asyncpg pool in THIS thread's event loop (WP-11 R6 fix)
        try:
            from app.persistence.engine import ensure_pool_initialized
            self._loop.run_until_complete(ensure_pool_initialized())
            logger.info("Database pool initialized in worker thread")
        except Exception as exc:
            logger.error("Failed to initialize database pool", extra={"error": str(exc)})

        # Start OutboxPublisher as a background task in this loop
        _outbox_task_ref = None
        self._outbox: OutboxPublisher | None = None
        try:
            from app.infra.outbox_publisher import OutboxPublisher
            outbox = OutboxPublisher(interval_seconds=5.0, batch_size=100)
            self._outbox = outbox

            async def _outbox_loop() -> None:
                try:
                    await outbox.start()
                    while outbox.running:
                        await asyncio.sleep(1)
                except asyncio.CancelledError:
                    pass
                finally:
                    await outbox.stop()

            _outbox_task_ref = self._loop.create_task(_outbox_loop())
            logger.info("Outbox publisher started in worker thread")

            # Start outbox health stats writer
            async def _outbox_health_loop() -> None:
                health_file = os.environ.get(
                    "OUTBOX_HEALTH_FILE", "/tmp/wisecut-agent-outbox-health.json"
                )
                while self._outbox and self._outbox.running:
                    try:
                        stats = self._outbox.get_stats()
                        tmp_file = health_file + ".tmp"
                        with open(tmp_file, "w") as f:
                            json.dump(stats, f)
                        os.replace(tmp_file, health_file)
                    except Exception:
                        pass
                    await asyncio.sleep(10)

            self._loop.create_task(_outbox_health_loop())
            logger.info("Outbox health stats writer started")
        except Exception as exc:
            logger.error("Failed to start outbox publisher", extra={"error": str(exc)})

        # Run startup recovery
        try:
            self._loop.run_until_complete(scan_and_recover())
        except Exception as exc:
            logger.exception("Recovery scan failed", extra={"error": str(exc)})

        # Main consume loop
        while not self._stop_event.is_set():
            try:
                self._consume_once()
            except Exception as exc:
                logger.error("Worker connection error", extra={"error": str(exc)})
                if self._stop_event.is_set():
                    break
                time.sleep(5)

    def _consume_once(self) -> None:
        """Connect, consume, and reconnect on failure."""
        from app.infra.messaging import RabbitMQConnection

        with RabbitMQConnection() as conn:
            self._connection = conn._connection
            self._channel = conn.channel
            ch = self._channel

            ch.basic_qos(prefetch_count=self._prefetch)
            ch.basic_consume(
                queue="maa.run.commands",
                on_message_callback=self._on_message,
            )
            logger.info("Worker consuming from maa.run.commands")

            while not self._stop_event.is_set():
                try:
                    assert self._connection is not None, "connection not established"
                    self._connection.process_data_events(time_limit=1.0)
                except pika.exceptions.ConnectionClosed:
                    logger.error("RabbitMQ connection lost, reconnecting...")
                    break
                except Exception as exc:
                    logger.error("Worker loop error", extra={"error": str(exc)})
                    if self._stop_event.is_set():
                        break
                    time.sleep(1)

    # ------------------------------------------------------------------
    # Message handler
    # ------------------------------------------------------------------

    def _on_message(
        self,
        ch: BlockingChannel,
        method: Basic.Deliver,
        properties: pika.BasicProperties,
        body: bytes,
    ) -> None:
        """Pika callback: runs in the worker thread.

        Schedules async processing on the event loop and blocks until
        the handler finishes, then acks/nacks from the same thread.
        """
        delivery_tag = method.delivery_tag

        try:
            message = json.loads(body)
        except json.JSONDecodeError:
            logger.error("Invalid RunCommand JSON", extra={"body": body[:200]})
            ch.basic_nack(delivery_tag=delivery_tag, requeue=False)
            return

        run_id = message.get("run_id", "")
        conversation_id = message.get("conversation_id", "")
        command_type = message.get("command_type", "")
        payload = message.get("payload", {})
        max_retries = message.get("max_retries", 3)
        attempt = message.get("attempt", 0)

        if not run_id or not conversation_id:
            logger.warning("Invalid RunCommand: missing run_id or conversation_id")
            ch.basic_ack(delivery_tag=delivery_tag)
            return

        # Schedule async processing and block until done
        loop = self._loop
        assert loop is not None, "event loop not set"
        result_future: asyncio.Future[None] = loop.create_future()

        async def _process() -> None:
            try:
                await self._process_run_command(
                    run_id=run_id,
                    conversation_id=conversation_id,
                    command_type=command_type,
                    payload=payload,
                    max_retries=max_retries,
                    attempt=attempt,
                    result_future=result_future,
                    loop=loop,
                )
            except Exception as exc:
                if not result_future.done():
                    result_future.set_exception(exc)

        loop.call_soon_threadsafe(
            lambda: loop.create_task(_process())
        )

        # Block the pika I/O thread until the handler completes
        try:
            loop.run_until_complete(result_future)
            ch.basic_ack(delivery_tag=delivery_tag)
        except _RetryMessage:
            # Publish to retry queue and ack the original
            from app.infra.messaging import QUEUE_RETRY
            ch.basic_publish(
                exchange="",
                routing_key=QUEUE_RETRY,
                body=json.dumps({
                    **payload,
                    "run_id": run_id,
                    "conversation_id": conversation_id,
                    "command_type": command_type,
                    "max_retries": max_retries,
                    "attempt": attempt + 1,
                }),
                properties=pika.BasicProperties(delivery_mode=2),
            )
            ch.basic_ack(delivery_tag=delivery_tag)
        except _DeadLetterMessage:
            ch.basic_nack(delivery_tag=delivery_tag, requeue=False)
            loop.run_until_complete(
                _update_run_status(run_id, "failed", "max_retries_exceeded")
            )
        except Exception as exc:
            logger.exception(
                "RunCommand processing failed",
                extra={"run_id": run_id, "error": str(exc)},
            )
            ch.basic_nack(delivery_tag=delivery_tag, requeue=False)
            loop.run_until_complete(
                _update_run_status(run_id, "failed", str(exc))
            )

    async def _process_run_command(
        self,
        run_id: str,
        conversation_id: str,
        command_type: str,
        payload: dict[str, Any],
        max_retries: int,
        attempt: int,
        result_future: asyncio.Future[None],
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        """Async processing: cancel check, lock, handler."""
        import redis.asyncio as aioredis

        redis_client = aioredis.from_url(settings.redis_url)
        cancel = CancelController(redis_client)

        try:
            # 1. Check cancel flag
            if await cancel.is_cancelled(run_id):
                logger.info("Run cancelled before processing", extra={"run_id": run_id})
                await _update_run_status(run_id, "cancelled")
                result_future.set_result(None)
                return

            # 2. Acquire conversation lock
            lock = await ConversationLock.acquire(redis_client, conversation_id, run_id)
            if lock is None:
                logger.warning(
                    "Conversation lock held, requeueing",
                    extra={"conversation_id": conversation_id},
                )
                # Signal retry by raising _RetryMessage
                raise _RetryMessage()

            await lock.start_heartbeat()

            try:
                # 3. Delegate to handler
                await self._handler(run_id, conversation_id, command_type, payload, loop)
                result_future.set_result(None)
            finally:
                await lock.release()

        except _RetryMessage:
            result_future.set_exception(_RetryMessage())
        except _DeadLetterMessage:
            result_future.set_exception(_DeadLetterMessage())
        except Exception as exc:
            if not result_future.done():
                result_future.set_exception(exc)
        finally:
            await redis_client.close()

    async def _default_handler(
        self,
        run_id: str,
        conversation_id: str,
        command_type: str,
        payload: dict[str, Any],
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        """Default no-op handler (WP-06 provides LangGraph execution)."""
        logger.info(
            "Default handler: no graph execution yet",
            extra={"run_id": run_id, "command_type": command_type},
        )
        await _update_run_status(run_id, "waiting_interaction")


# ---------------------------------------------------------------------------
# Control flow exceptions (internal, not for external use)
# ---------------------------------------------------------------------------


class _RetryMessage(Exception):
    """Signal to requeue the message."""
    pass


class _DeadLetterMessage(Exception):
    """Signal to send the message to the DLQ."""
    pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _update_run_status(run_id: str, status: str, error: str | None = None) -> None:
    """Update run status in the database."""
    from app.persistence.engine import get_session_factory
    from app.persistence.repositories import RunRepository

    factory = get_session_factory()
    async with factory() as session:
        repo = RunRepository(session)
        if status in ("completed", "failed", "cancelled"):
            await repo.mark_finished(run_id, status, error)
        else:
            await repo.update_status(run_id, status)
        await session.commit()


def start_worker_thread(run_handler: RunHandler | None = None) -> RunWorker:
    """Create and start the worker thread.

    Call this from the application lifespan to enable background processing.
    """
    worker = RunWorker(run_handler=run_handler)
    worker.start()
    return worker
