"""Application services for MAA API business logic.

Services coordinate repositories, enforce business rules, and produce events.
They are called by API routers and (later) by the Worker.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from app.persistence.unit_of_work import UnitOfWork
from app.protocol.sse import encode_sse_event, is_terminal_event

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Conversation Service
# ---------------------------------------------------------------------------

class ConversationService:
    """Business logic for Conversation aggregate."""

    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow
        self._conversations = uow.conversations

    async def create(
        self,
        title: str,
        user_id: str,
        project_id: str,
        profile_id: str = "one-click-quick",
        mode: str = "quick",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create a new conversation.

        Returns the MAA-compatible response dict.
        """
        conversation_id = f"conv-{uuid4().hex[:12]}"
        meta = metadata or {}
        meta.update({
            "user_id": user_id,
            "project_id": project_id,
            "mode": mode,
            "agent_profile_id": profile_id,
        })

        conv = await self._conversations.create(
            conversation_id=conversation_id,
            user_id=user_id,
            project_id=project_id,
            profile_id=profile_id,
            title=title,
            metadata=meta,
        )

        logger.info(
            "Conversation created",
            extra={"conversation_id": conversation_id, "user_id": user_id, "project_id": project_id},
        )

        return {
            "conversation_id": conv.id,
            "langgraph_thread_id": conv.id,
            "status": conv.status,
        }

    async def get_detail(self, conversation_id: str) -> dict[str, Any] | None:
        """Get conversation detail snapshot."""
        detail = await self._conversations.get_detail(conversation_id)
        if detail is None:
            return None

        conv = detail["conversation"]
        active_run = detail["active_run"]
        messages = detail["messages"]
        interactions = detail["interactions"]
        recent_events = detail["recent_events"]

        # Serialize
        def _serialize_message(msg) -> dict:
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

        def _serialize_interaction(inter) -> dict:
            return {
                "id": inter.id,
                "conversation_id": inter.conversation_id,
                "run_id": inter.run_id,
                "status": inter.status,
                "intent": inter.intent,
                "payload": inter.payload_json,
                "answer": inter.answer_json,
                "version": inter.version,
                "requested_at": inter.requested_at.isoformat() if inter.requested_at else None,
                "resolved_at": inter.resolved_at.isoformat() if inter.resolved_at else None,
            }

        def _serialize_event(evt) -> dict:
            return {
                "id": evt.id,
                "run_id": evt.run_id,
                "seq": evt.seq,
                "type": evt.event_type,
                "payload": evt.payload_json,
                "visible": evt.visible,
                "created_at": evt.created_at.isoformat() if evt.created_at else None,
            }

        def _serialize_run(run) -> dict | None:
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

        return {
            "conversation": {
                "id": conv.id,
                "status": conv.status,
                "metadata": conv.metadata_json or {},
            },
            "active_run": _serialize_run(active_run),
            "messages": [_serialize_message(m) for m in messages],
            "interactions": [_serialize_interaction(i) for i in interactions],
            "recent_events": [_serialize_event(e) for e in recent_events],
        }


# ---------------------------------------------------------------------------
# Message Service
# ---------------------------------------------------------------------------

class MessageService:
    """Business logic for Message aggregate with idempotency."""

    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow
        self._messages = uow.messages
        self._runs = uow.runs
        self._events = uow.events
        self._outbox = uow.outbox

    async def post_message(
        self,
        conversation_id: str,
        run_id: str,
        message_type: str,
        content: str,
        role: str = "user",
        metadata: dict[str, Any] | None = None,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        """Post a message to a conversation.

        Enforces idempotency via request_id.
        """
        # Idempotency check
        if request_id:
            existing = await self._messages.get_by_request_id(conversation_id, request_id)
            if existing:
                logger.info(
                    f"Duplicate message request_id={request_id}, returning existing",
                    extra={"message_id": existing.id},
                )
                return {
                    "conversation_id": conversation_id,
                    "run_id": existing.run_id or run_id,
                    "accepted_as_inbox": True,
                    "events_url": f"/runs/{existing.run_id or run_id}/events",
                }

        message_id = f"msg-{uuid4().hex[:12]}"
        _msg = await self._messages.create(
            message_id=message_id,
            conversation_id=conversation_id,
            run_id=run_id,
            role=role,
            content=content,
            message_type=message_type,
            metadata=metadata or {},
            request_id=request_id,
        )

        # Enqueue run command for Worker processing (Outbox pattern)
        await self._outbox.enqueue(
            aggregate_type="run",
            aggregate_id=run_id,
            event_type="run.command",
            payload={
                "run_id": run_id,
                "conversation_id": conversation_id,
                "command_type": message_type,
                "payload": {"content": content, "message_id": message_id},
                "max_retries": 3,
                "attempt": 0,
            },
        )

        logger.info(
            "Message posted",
            extra={
                "message_id": message_id,
                "conversation_id": conversation_id,
                "run_id": run_id,
                "type": message_type,
            },
        )

        return {
            "conversation_id": conversation_id,
            "run_id": run_id,
            "accepted_as_inbox": True,
            "events_url": f"/runs/{run_id}/events",
        }

    async def post_interaction_response(
        self,
        conversation_id: str,
        run_id: str,
        interaction_id: str,
        action: str,
        content: Any,
        client_action_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Post an interaction response.

        This is a specialized message posting that also resolves the interaction.
        """
        # Use client_action_id as request_id for idempotency
        request_id = f"interaction:{interaction_id}:{client_action_id}"

        # Check idempotency
        existing = await self._messages.get_by_request_id(conversation_id, request_id)
        if existing:
            logger.info(
                f"Duplicate interaction response client_action_id={client_action_id}",
                extra={"message_id": existing.id},
            )
            return {
                "conversation_id": conversation_id,
                "run_id": run_id,
                "accepted_as_inbox": True,
                "events_url": f"/runs/{run_id}/events",
            }

        # Build the interaction response content
        if isinstance(content, str):
            try:
                content_obj = json.loads(content)
            except json.JSONDecodeError:
                content_obj = {"value": content}
        else:
            content_obj = content

        message_id = f"msg-{uuid4().hex[:12]}"
        _msg = await self._messages.create(
            message_id=message_id,
            conversation_id=conversation_id,
            run_id=run_id,
            role="user",
            content=json.dumps(content_obj) if isinstance(content_obj, (dict, list)) else str(content_obj),
            message_type="interaction_response",
            metadata={
                "interaction_id": interaction_id,
                "action": action,
                "client_action_id": client_action_id,
                **(metadata or {}),
            },
            request_id=request_id,
        )

        # Resolve the interaction
        interactions = self._uow.interactions
        await interactions.resolve(
            interaction_id=interaction_id,
            action=action,
            answer={
                "action": action,
                "content": content_obj,
                "client_action_id": client_action_id,
                "resolved_at": datetime.now(UTC).isoformat(),
            },
        )

        # Emit interaction.resolved event
        event_repo = self._uow.events
        seq = await event_repo.get_next_seq(conversation_id, run_id)
        await event_repo.create(
            event_id=f"evt-{uuid4().hex[:12]}",
            conversation_id=conversation_id,
            run_id=run_id,
            seq=seq,
            event_type="interaction.resolved",
            payload={
                "interaction_id": interaction_id,
                "run_id": run_id,
                "action": action,
                "status": "answered",
                "value": content_obj,
                "client_action_id": client_action_id,
                "resolved_at": datetime.now(UTC).isoformat(),
            },
        )

        logger.info(
            "Interaction response posted",
            extra={
                "interaction_id": interaction_id,
                "action": action,
                "run_id": run_id,
                "message_id": message_id,
            },
        )

        return {
            "conversation_id": conversation_id,
            "run_id": run_id,
            "accepted_as_inbox": True,
            "events_url": f"/runs/{run_id}/events",
        }


# ---------------------------------------------------------------------------
# Run Service
# ---------------------------------------------------------------------------

class RunService:
    """Business logic for Run aggregate."""

    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow
        self._runs = uow.runs
        self._events = uow.events

    async def create_run(
        self,
        conversation_id: str,
        run_id: str,
        graph_thread_id: str | None = None,
    ) -> dict[str, Any]:
        """Create a new run and emit run.started event."""
        run = await self._runs.create(
            run_id=run_id,
            conversation_id=conversation_id,
            graph_thread_id=graph_thread_id or conversation_id,
        )

        # Mark as started immediately
        await self._runs.mark_started(run_id)

        # Emit run.started event
        seq = await self._events.get_next_seq(conversation_id, run_id)
        await self._events.create(
            event_id=f"evt-{uuid4().hex[:12]}",
            conversation_id=conversation_id,
            run_id=run_id,
            seq=seq,
            event_type="run.started",
            payload={
                "run_id": run_id,
                "conversation_id": conversation_id,
                "status": "running",
                "phase": "starting",
                "started_at": datetime.now(UTC).isoformat(),
            },
        )

        logger.info(
            "Run created and started",
            extra={"run_id": run_id, "conversation_id": conversation_id},
        )

        return {
            "run_id": run_id,
            "conversation_id": conversation_id,
            "status": "running",
            "phase": "starting",
            "started_at": run.started_at.isoformat() if run.started_at else None,
        }

    async def cancel_run(self, run_id: str) -> dict[str, Any]:
        """Request cancellation of a run."""
        run = await self._runs.request_cancel(run_id)
        if run is None:
            from app.core.exceptions import RunNotFound
            raise RunNotFound(run_id)

        if run.status in ("completed", "failed", "cancelled"):
            from app.core.exceptions import RunTerminalError
            raise RunTerminalError(run_id, run.status)

        # Emit run.cancelled event
        conversation_id = run.conversation_id
        seq = await self._events.get_next_seq(conversation_id, run_id)
        await self._events.create(
            event_id=f"evt-{uuid4().hex[:12]}",
            conversation_id=conversation_id,
            run_id=run_id,
            seq=seq,
            event_type="run.cancelled",
            payload={
                "run_id": run_id,
                "status": "cancelled",
                "finished_at": datetime.now(UTC).isoformat(),
            },
        )

        # Update run status
        await self._runs.mark_finished(run_id, "cancelled")

        logger.info(
            "Run cancelled",
            extra={"run_id": run_id, "conversation_id": conversation_id},
        )

        return {"run_id": run_id, "status": "cancelled"}


# ---------------------------------------------------------------------------
# Event Service
# ---------------------------------------------------------------------------

class EventService:
    """Business logic for Event aggregate and SSE streaming."""

    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow
        self._events = uow.events

    async def get_events_for_sse(
        self,
        run_id: str,
        after_seq: int = 0,
    ) -> AsyncGenerator[str, None]:
        """Generate SSE event stream for a run.

        Yields SSE-formatted event strings matching the Go Client's expectations.
        """
        # Get all events for this run after after_seq
        events = await self._events.get_by_run(run_id, after_seq=after_seq)

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

            # If this is a terminal event, stop streaming
            if is_terminal_event(event.event_type):
                return

    async def emit_event(
        self,
        conversation_id: str,
        run_id: str,
        event_type: str,
        payload: dict[str, Any],
    ) -> int:
        """Emit a new event and persist it."""
        seq = await self._events.get_next_seq(conversation_id, run_id)
        event_id = f"evt-{uuid4().hex[:12]}"
        await self._events.create(
            event_id=event_id,
            conversation_id=conversation_id,
            run_id=run_id,
            seq=seq,
            event_type=event_type,
            payload=payload,
            visible=True,
        )
        logger.debug(
            f"Event emitted: {event_type}",
            extra={"event_id": event_id, "run_id": run_id, "seq": seq},
        )
        return seq
