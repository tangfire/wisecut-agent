"""RabbitMQ infrastructure: connection, exchange, and queue declarations.

Topology (mirrors plan.md §10.1):
  Exchange:  maa.exchange  (fanout, durable)
  Queue:     maa.run.commands      (durable, DLQ → maa.run.commands.dlq)
  Queue:     maa.run.commands.retry (durable, TTL 30s, DLQ → maa.run.commands.dlq)
  Queue:     maa.run.commands.dlq  (durable)

Usage:
    async with RabbitMQConnection(settings) as conn:
        channel = await conn.get_channel()
        await channel.basic_publish(...)
"""

from __future__ import annotations

import json
import logging
from typing import Any

import pika
from pika.adapters.blocking_connection import BlockingChannel

from app.settings import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Topology constants
# ---------------------------------------------------------------------------

EXCHANGE_NAME = "maa.exchange"
EXCHANGE_TYPE = "fanout"

QUEUE_RUN_COMMANDS = "maa.run.commands"
QUEUE_RETRY = "maa.run.commands.retry"
QUEUE_DLQ = "maa.run.commands.dlq"

ROUTING_KEY_RUN = "run.command"
ROUTING_KEY_RETRY = "run.command.retry"

RETRY_TTL_MS = 30_000  # 30 seconds before retry queue forwards to DLQ


# ---------------------------------------------------------------------------
# Connection management
# ---------------------------------------------------------------------------


class RabbitMQConnection:
    """Wrapper around pika blocking connection for Worker use.

    RabbitMQ operations in the Worker run in a dedicated thread, so a
    synchronous blocking connection is acceptable here.  The API process
    never calls this directly.
    """

    def __init__(self, url: str | None = None) -> None:
        self._url = url or settings.rabbitmq_url
        self._connection: pika.BlockingConnection | None = None
        self._channel: BlockingChannel | None = None

    def connect(self) -> None:
        """Establish blocking connection and declare topology."""
        self._connection = pika.BlockingConnection(
            pika.URLParameters(self._url)
        )
        self._channel = self._connection.channel()
        self._declare_topology()
        logger.info("RabbitMQ connected", extra={"url": self._url})

    def _declare_topology(self) -> None:
        """Declare exchange, queues, and bindings."""
        ch = self._channel
        if ch is None:
            raise RuntimeError("RabbitMQ channel not initialized")

        # Exchange
        ch.exchange_declare(
            exchange=EXCHANGE_NAME,
            exchange_type=EXCHANGE_TYPE,
            durable=True,
        )

        # Retry queue with TTL and dead-letter routing
        ch.queue_declare(queue=QUEUE_RETRY, durable=True, arguments={
            "x-message-ttl": RETRY_TTL_MS,
            "x-dead-letter-exchange": "",
            "x-dead-letter-routing-key": QUEUE_DLQ,
        })

        # DLQ
        ch.queue_declare(queue=QUEUE_DLQ, durable=True)

        # Main run commands queue with DLQ alternate
        ch.queue_declare(queue=QUEUE_RUN_COMMANDS, durable=True, arguments={
            "x-dead-letter-exchange": "",
            "x-dead-letter-routing-key": QUEUE_RETRY,
        })

        # Bindings
        ch.queue_bind(exchange=EXCHANGE_NAME, queue=QUEUE_RUN_COMMANDS,
                      routing_key=ROUTING_KEY_RUN)
        ch.queue_bind(exchange=EXCHANGE_NAME, queue=QUEUE_RETRY,
                      routing_key=ROUTING_KEY_RETRY)

        logger.info(
            "RabbitMQ topology declared",
            extra={
                "exchange": EXCHANGE_NAME,
                "queues": [QUEUE_RUN_COMMANDS, QUEUE_RETRY, QUEUE_DLQ],
            },
        )

    @property
    def channel(self) -> BlockingChannel:
        if self._channel is None:
            raise RuntimeError("RabbitMQ not connected")
        return self._channel

    def close(self) -> None:
        if self._channel and self._channel.is_open:
            try:
                self._channel.close()
            except Exception:
                pass
        if self._connection and self._connection.is_open:
            try:
                self._connection.close()
            except Exception:
                pass
        self._channel = None
        self._connection = None

    def __enter__(self) -> RabbitMQConnection:
        self.connect()
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()


# ---------------------------------------------------------------------------
# Publish helpers
# ---------------------------------------------------------------------------


def publish_run_command(
    ch: BlockingChannel,
    run_id: str,
    conversation_id: str,
    command_type: str,
    payload: dict[str, Any],
    priority: int = 0,
    max_retries: int = 3,
) -> None:
    """Publish a Run command to the durable queue.

    The message is idempotent-keyed by (conversation_id, run_id, command_type).
    """
    message = {
        "run_id": run_id,
        "conversation_id": conversation_id,
        "command_type": command_type,
        "payload": payload,
        "max_retries": max_retries,
        "attempt": 0,
    }

    ch.basic_publish(
        exchange=EXCHANGE_NAME,
        routing_key=ROUTING_KEY_RUN,
        body=json.dumps(message, ensure_ascii=False),
        properties=pika.BasicProperties(
            delivery_mode=2,  # persistent
            priority=priority,
            content_type="application/json",
        ),
    )
    logger.debug(
        "Run command published",
        extra={"run_id": run_id, "command_type": command_type},
    )


def publish_event(
    ch: BlockingChannel,
    event_type: str,
    payload: dict[str, Any],
    exchange: str = EXCHANGE_NAME,
    routing_key: str = "",
) -> None:
    """Publish a domain event to the exchange."""
    ch.basic_publish(
        exchange=exchange,
        routing_key=routing_key,
        body=json.dumps({"event_type": event_type, "payload": payload}, ensure_ascii=False),
        properties=pika.BasicProperties(
            delivery_mode=2,
            content_type="application/json",
        ),
    )


# ---------------------------------------------------------------------------
# Consumer helpers
# ---------------------------------------------------------------------------


def consume_messages(
    ch: BlockingChannel,
    queue: str,
    on_message: Any,
    prefetch_count: int = 1,
) -> None:
    """Start consuming messages from a queue.

    Args:
        ch: RabbitMQ channel.
        queue: Queue name.
        on_message: Callback receiving (method, properties, body).
        prefetch_count: QoS prefetch count (fair dispatch).
    """
    ch.basic_qos(prefetch_count=prefetch_count)
    ch.basic_consume(queue=queue, on_message_callback=on_message)
    logger.info("Starting consumer", extra={"queue": queue})
    try:
        ch.start_consuming()
    except KeyboardInterrupt:
        ch.stop_consuming()
        logger.info("Consumer stopped", extra={"queue": queue})
