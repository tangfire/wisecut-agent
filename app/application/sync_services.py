"""Synchronous application services for the API process.

These services use synchronous SQLAlchemy sessions (psycopg2/sqlite3) to
avoid the asyncpg event loop conflict under uvicorn/anyio in Docker.

The Worker process uses the async services in app/application/services.py
with asyncpg in its own dedicated event loop.

Architecture (plan.md section 10.1):
  API process  → sync DB access via app/persistence/sync_engine.py
  Worker process → async DB access via app/persistence/engine.py (asyncpg)
"""

from __future__ import annotations

import json
import logging
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any
from uuid import uuid4

from app.persistence.sync_engine import get_sync_session_factory
from app.protocol.sse import encode_sse_event, is_terminal_event

logger = logging.getLogger(__name__)


@contextmanager
def _sync_session() -> Generator[Any, None, None]:
    """Context manager for a synchronous DB session."""
    factory = get_sync_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Conversation Service (sync)
# ---------------------------------------------------------------------------

class APIConversationService:
    """Synchronous conversation service for the API process."""

    def create(
        self,
        title: str,
        user_id: str,
        project_id: str,
        profile_id: str = "one-click-quick",
        mode: str = "quick",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create a new conversation."""
        from app.persistence.models import Conversation

        conversation_id = f"conv-{uuid4().hex[:12]}"
        meta = metadata or {}
        meta.update({
            "user_id": user_id,
            "project_id": project_id,
            "mode": mode,
            "agent_profile_id": profile_id,
        })

        with _sync_session() as session:
            conv = Conversation(
                id=conversation_id,
                user_id=user_id,
                project_id=project_id,
                profile_id=profile_id,
                title=title,
                status="created",
                metadata_json=meta,
            )
            session.add(conv)
            session.commit()
            session.refresh(conv)

        logger.info(
            "Conversation created (sync)",
            extra={"conversation_id": conversation_id},
        )
        return {
            "conversation_id": conv.id,
            "langgraph_thread_id": conv.id,
            "status": conv.status,
        }

    def get_by_id(self, conversation_id: str) -> Any | None:
        """Get conversation by ID."""
        from app.persistence.models import Conversation
        with _sync_session() as session:
            return session.get(Conversation, conversation_id)

    def get_detail(self, conversation_id: str) -> dict[str, Any] | None:
        """Get conversation detail snapshot."""
        from app.persistence.models import Conversation, Message, Run

        with _sync_session() as session:
            conv = session.get(Conversation, conversation_id)
            if conv is None:
                return None

            active_run = session.query(Run).filter(
                Run.conversation_id == conversation_id,
                Run.status.notin_(["completed", "failed", "cancelled"]),
            ).first()

            messages = session.query(Message).filter(
                Message.conversation_id == conversation_id
            ).order_by(Message.created_at.desc()).limit(50).all()

            return {
                "conversation": {
                    "id": conv.id,
                    "status": conv.status,
                    "metadata": conv.metadata_json or {},
                },
                "active_run": _serialize_run(active_run),
                "messages": [_serialize_message(m) for m in messages],
                "interactions": [],
                "recent_events": [],
            }


def _serialize_message(msg: Any) -> dict[str, Any]:
    return {
        "id": msg.id,
        "conversation_id": msg.conversation_id,
        "run_id": msg.run_id,
        "role": msg.role,
        "type": msg.type,
        "content": msg.content,
        "metadata": msg.metadata_json or {},
        "created_at": msg.created_at.isoformat() if msg.created_at else None,
    }


def _serialize_run(run: Any) -> dict[str, Any] | None:
    if run is None:
        return None
    return {
        "id": run.id,
        "conversation_id": run.conversation_id,
        "status": run.status,
        "phase": run.phase,
        "error": run.error_message or "",
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "ended_at": run.finished_at.isoformat() if run.finished_at else None,
    }


# ---------------------------------------------------------------------------
# Message Service (sync) — publishes to RabbitMQ
# ---------------------------------------------------------------------------

class APIMessageService:
    """API message service: publishes Run commands to RabbitMQ.

    The Worker process handles all database writes for messages.
    """

    def post_message(
        self,
        conversation_id: str,
        message_type: str,
        content: str | dict[str, Any],
        role: str = "user",
        metadata: dict[str, Any] | None = None,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        """Post a message: create Run and Message in DB, then publish to RabbitMQ."""
        from app.infra.messaging import publish_run_command
        from app.settings import settings

        run_id = f"run-{uuid4().hex[:12]}"
        message_id = f"msg-{uuid4().hex[:12]}"

        # Serialize dict content to JSON string for DB storage
        if isinstance(content, dict):
            content_str = json.dumps(content, ensure_ascii=False)
        else:
            content_str = content

        # Create Run and Message in database first (Worker needs Run to exist)
        with _sync_session() as session:
            from app.persistence.models import Message, Run
            run = Run(
                id=run_id,
                conversation_id=conversation_id,
                status="running",
                phase="starting",
                graph_thread_id=conversation_id,
            )
            session.add(run)
            msg = Message(
                id=message_id,
                conversation_id=conversation_id,
                run_id=run_id,
                role=role,
                type=message_type,
                content=content_str,
                metadata_json=metadata or {},
            )
            session.add(msg)
            session.commit()

        # Publish Run command to RabbitMQ
        import pika
        params = pika.URLParameters(settings.rabbitmq_url)
        with pika.BlockingConnection(params) as conn:
            ch = conn.channel()
            publish_run_command(
                ch,
                run_id=run_id,
                conversation_id=conversation_id,
                command_type=message_type,
                payload={
                    "content": content,
                    "message_id": message_id,
                    "message_type": message_type,
                    "role": role,
                    "request_id": request_id,
                    "metadata": metadata or {},
                },
            )

        logger.info(
            "Run command published (API->RabbitMQ)",
            extra={"run_id": run_id, "conversation_id": conversation_id},
        )
        return {
            "conversation_id": conversation_id,
            "run_id": run_id,
            "accepted_as_inbox": True,
            "events_url": f"/runs/{run_id}/events",
        }

    def post_interaction_response(
        self,
        conversation_id: str,
        run_id: str,
        interaction_id: str,
        action: str,
        content: Any,
        client_action_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Post interaction response: publish to RabbitMQ."""
        from app.infra.messaging import publish_run_command
        from app.settings import settings

        if isinstance(content, str):
            try:
                content_obj = json.loads(content)
            except json.JSONDecodeError:
                content_obj = {"value": content}
        else:
            content_obj = content

        request_id = f"interaction:{interaction_id}:{client_action_id}"
        payload = {
            "run_id": run_id,
            "conversation_id": conversation_id,
            "command_type": "interaction_response",
            "payload": {
                "interaction_id": interaction_id,
                "action": action,
                "content": content_obj,
                "client_action_id": client_action_id,
                "request_id": request_id,
                "metadata": {
                    "interaction_id": interaction_id,
                    "action": action,
                    "client_action_id": client_action_id,
                    **(metadata or {}),
                },
            },
        }

        import pika
        params = pika.URLParameters(settings.rabbitmq_url)
        with pika.BlockingConnection(params) as conn:
            ch = conn.channel()
            publish_run_command(
                ch,
                run_id=run_id,
                conversation_id=conversation_id,
                command_type="interaction_response",
                payload=payload,
            )

        return {
            "conversation_id": conversation_id,
            "run_id": run_id,
            "accepted_as_inbox": True,
            "events_url": f"/runs/{run_id}/events",
        }


# ---------------------------------------------------------------------------
# Event Service (sync reads for SSE)
# ---------------------------------------------------------------------------

class APIEventService:
    """API event service: reads events from DB for SSE (sync)."""

    def get_events_for_sse(self, run_id: str, after_seq: int = 0) -> Generator[str, None, None]:
        """Generate SSE event stream for a run (sync)."""
        from app.persistence.models import Event

        with _sync_session() as session:
            events = session.query(Event).filter(
                Event.run_id == run_id,
                Event.seq > after_seq,
            ).order_by(Event.seq.asc()).all()

            for event in events:
                sse = encode_sse_event(
                    event_id=event.id,
                    event_type=event.event_type,
                    data={
                        **event.payload_json,
                        "seq": event.seq,
                        "conversation_id": event.conversation_id,
                        "maa_run_id": run_id,
                    },
                )
                yield sse

                if is_terminal_event(event.event_type):
                    return

    def emit_event(
        self,
        conversation_id: str,
        run_id: str,
        event_type: str,
        payload: dict[str, Any],
    ) -> int:
        """Emit a new event and persist it (sync)."""
        from app.persistence.models import Event

        with _sync_session() as session:
            max_seq = session.query(Event.seq).filter(
                Event.run_id == run_id
            ).order_by(Event.seq.desc()).first()
            seq = (max_seq[0] + 1) if max_seq else 0

            event_id = f"evt-{uuid4().hex[:12]}"
            event = Event(
                id=event_id,
                conversation_id=conversation_id,
                run_id=run_id,
                seq=seq,
                event_type=event_type,
                payload_json=payload,
                visible=True,
            )
            session.add(event)
            session.commit()
            return seq
