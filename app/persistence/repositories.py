"""Repository implementations for all aggregates.

Each repository provides CRUD + domain-specific queries for one aggregate root.
All methods are async and use the async session from the Unit of Work.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.models import (
    Approval,
    Artifact,
    AuditLog,
    Checkpoint,
    Conversation,
    Event,
    Interaction,
    Message,
    OutboxEvent,
    Run,
    ToolExecution,
)

# ---------------------------------------------------------------------------
# Base Repository
# ---------------------------------------------------------------------------

class BaseRepository:
    """Common helpers for all repositories."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _now(self) -> datetime:
        return datetime.now(UTC)


# ---------------------------------------------------------------------------
# Conversation Repository
# ---------------------------------------------------------------------------

class ConversationRepository(BaseRepository):
    """Repository for Conversation aggregate."""

    async def create(
        self,
        conversation_id: str,
        user_id: str,
        project_id: str,
        profile_id: str,
        title: str,
        metadata: dict[str, Any] | None = None,
    ) -> Conversation:
        conv = Conversation(
            id=conversation_id,
            user_id=user_id,
            project_id=project_id,
            profile_id=profile_id,
            title=title,
            status="created",
            metadata_json=metadata or {},
        )
        self._session.add(conv)
        await self._session.flush()
        return conv

    async def get_by_id(self, conversation_id: str) -> Conversation | None:
        result = await self._session.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
        return result.scalar_one_or_none()

    async def get_detail(self, conversation_id: str) -> dict | None:
        """Return conversation detail with active_run, messages, interactions, events."""
        conv = await self.get_by_id(conversation_id)
        if not conv:
            return None

        # Active run
        active_run_result = await self._session.execute(
            select(Run)
            .where(Run.conversation_id == conversation_id)
            .where(Run.status.in_(["queued", "running", "waiting_interaction", "waiting_approval", "rendering"]))
            .order_by(desc(Run.created_at))
            .limit(1)
        )
        active_run = active_run_result.scalar_one_or_none()

        # Recent messages
        messages_result = await self._session.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(desc(Message.created_at))
            .limit(50)
        )
        messages = list(reversed(messages_result.scalars().all()))

        # Recent interactions
        interactions_result = await self._session.execute(
            select(Interaction)
            .where(Interaction.conversation_id == conversation_id)
            .order_by(desc(Interaction.requested_at))
            .limit(10)
        )
        interactions = list(reversed(interactions_result.scalars().all()))

        # Recent events
        events_result = await self._session.execute(
            select(Event)
            .where(Event.conversation_id == conversation_id)
            .order_by(desc(Event.created_at))
            .limit(20)
        )
        recent_events = list(reversed(events_result.scalars().all()))

        return {
            "conversation": conv,
            "active_run": active_run,
            "messages": messages,
            "interactions": interactions,
            "recent_events": recent_events,
        }

    async def update_status(self, conversation_id: str, status: str) -> Conversation | None:
        conv = await self.get_by_id(conversation_id)
        if conv:
            conv.status = status
            conv.updated_at = self._now()
            await self._session.flush()
        return conv


# ---------------------------------------------------------------------------
# Run Repository
# ---------------------------------------------------------------------------

class RunRepository(BaseRepository):
    """Repository for Run aggregate."""

    async def create(
        self,
        run_id: str,
        conversation_id: str,
        graph_thread_id: str | None = None,
    ) -> Run:
        run = Run(
            id=run_id,
            conversation_id=conversation_id,
            status="queued",
            phase="starting",
            graph_thread_id=graph_thread_id or conversation_id,
        )
        self._session.add(run)
        await self._session.flush()
        return run

    async def get_by_id(self, run_id: str) -> Run | None:
        result = await self._session.execute(select(Run).where(Run.id == run_id))
        return result.scalar_one_or_none()

    async def get_active_run(self, conversation_id: str) -> Run | None:
        result = await self._session.execute(
            select(Run)
            .where(Run.conversation_id == conversation_id)
            .where(Run.status.in_(["queued", "running", "waiting_interaction", "waiting_approval", "rendering"]))
            .order_by(desc(Run.created_at))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def update_status(self, run_id: str, status: str) -> Run | None:
        run = await self.get_by_id(run_id)
        if run:
            run.status = status
            await self._session.flush()
        return run

    async def mark_started(self, run_id: str) -> Run | None:
        run = await self.get_by_id(run_id)
        if run:
            run.status = "running"
            run.started_at = self._now()
            await self._session.flush()
        return run

    async def mark_finished(self, run_id: str, status: str, error: str | None = None) -> Run | None:
        run = await self.get_by_id(run_id)
        if run:
            run.status = status
            run.finished_at = self._now()
            if error:
                run.error_message = error
            await self._session.flush()
        return run

    async def request_cancel(self, run_id: str) -> Run | None:
        run = await self.get_by_id(run_id)
        if run and run.status not in ("completed", "failed", "cancelled"):
            run.cancel_requested_at = self._now()
            await self._session.flush()
        return run

    async def mark_waiting_interaction(self, run_id: str) -> Run | None:
        run = await self.get_by_id(run_id)
        if run:
            run.status = "waiting_interaction"
            run.phase = "awaiting_user_input"
            await self._session.flush()
        return run

    async def mark_waiting_approval(self, run_id: str) -> Run | None:
        run = await self.get_by_id(run_id)
        if run:
            run.status = "waiting_approval"
            run.phase = "awaiting_approval"
            await self._session.flush()
        return run

    async def mark_rendering(self, run_id: str) -> Run | None:
        run = await self.get_by_id(run_id)
        if run:
            run.status = "rendering"
            run.phase = "rendering"
            await self._session.flush()
        return run


# ---------------------------------------------------------------------------
# Message Repository
# ---------------------------------------------------------------------------

class MessageRepository(BaseRepository):
    """Repository for Message aggregate."""

    async def create(
        self,
        message_id: str,
        conversation_id: str,
        role: str,
        content: str,
        run_id: str | None = None,
        message_type: str | None = None,
        metadata: dict[str, Any] | None = None,
        request_id: str | None = None,
    ) -> Message:
        msg = Message(
            id=message_id,
            conversation_id=conversation_id,
            run_id=run_id,
            role=role,
            type=message_type,
            content=content,
            metadata_json=metadata or {},
            request_id=request_id,
        )
        self._session.add(msg)
        await self._session.flush()
        return msg

    async def get_by_conversation(self, conversation_id: str) -> Sequence[Message]:
        result = await self._session.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at)
        )
        return result.scalars().all()

    async def get_by_request_id(self, conversation_id: str, request_id: str) -> Message | None:
        result = await self._session.execute(
            select(Message).where(
                Message.conversation_id == conversation_id,
                Message.request_id == request_id,
            )
        )
        return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# Event Repository
# ---------------------------------------------------------------------------

class EventRepository(BaseRepository):
    """Repository for Event aggregate."""

    async def create(
        self,
        event_id: str,
        conversation_id: str,
        run_id: str,
        seq: int,
        event_type: str,
        payload: dict[str, Any],
        visible: bool = True,
        source: str = "maa",
        idempotency_key: str | None = None,
    ) -> Event:
        event = Event(
            id=event_id,
            conversation_id=conversation_id,
            run_id=run_id,
            seq=seq,
            event_type=event_type,
            payload_json=payload,
            visible=visible,
            source=source,
            idempotency_key=idempotency_key,
        )
        self._session.add(event)
        await self._session.flush()
        return event

    async def get_by_run(self, run_id: str, after_seq: int = 0) -> Sequence[Event]:
        result = await self._session.execute(
            select(Event)
            .where(Event.run_id == run_id, Event.seq > after_seq)
            .order_by(Event.seq)
        )
        return result.scalars().all()

    async def get_next_seq(self, conversation_id: str, run_id: str) -> int:
        """Get the next sequence number for a run (atomic)."""
        result = await self._session.execute(
            select(func.coalesce(func.max(Event.seq), 0)).where(
                Event.conversation_id == conversation_id,
                Event.run_id == run_id,
            )
        )
        return result.scalar_one() + 1


# ---------------------------------------------------------------------------
# Interaction Repository
# ---------------------------------------------------------------------------

class InteractionRepository(BaseRepository):
    """Repository for Interaction aggregate."""

    async def create(
        self,
        interaction_id: str,
        conversation_id: str,
        run_id: str,
        intent: str,
        payload: dict[str, Any],
    ) -> Interaction:
        interaction = Interaction(
            id=interaction_id,
            conversation_id=conversation_id,
            run_id=run_id,
            intent=intent,
            payload_json=payload,
            status="pending",
        )
        self._session.add(interaction)
        await self._session.flush()
        return interaction

    async def get_by_id(self, interaction_id: str) -> Interaction | None:
        result = await self._session.execute(
            select(Interaction).where(Interaction.id == interaction_id)
        )
        return result.scalar_one_or_none()

    async def resolve(
        self,
        interaction_id: str,
        action: str,
        answer: dict[str, Any],
    ) -> Interaction | None:
        interaction = await self.get_by_id(interaction_id)
        if interaction:
            interaction.status = "answered"
            interaction.answer_json = answer
            interaction.resolved_at = self._now()
            await self._session.flush()
        return interaction


# ---------------------------------------------------------------------------
# Approval Repository
# ---------------------------------------------------------------------------

class ApprovalRepository(BaseRepository):
    """Repository for Approval aggregate."""

    async def create(
        self,
        approval_id: str,
        conversation_id: str,
        run_id: str,
        tool_name: str,
        arguments: dict[str, Any],
        expires_at: datetime | None = None,
    ) -> Approval:
        approval = Approval(
            id=approval_id,
            conversation_id=conversation_id,
            run_id=run_id,
            tool_name=tool_name,
            arguments_json=arguments,
            status="pending",
            expires_at=expires_at,
        )
        self._session.add(approval)
        await self._session.flush()
        return approval

    async def get_by_id(self, approval_id: str) -> Approval | None:
        result = await self._session.execute(
            select(Approval).where(Approval.id == approval_id)
        )
        return result.scalar_one_or_none()

    async def decide(
        self,
        approval_id: str,
        decision: str,
        decision_data: dict[str, Any] | None = None,
    ) -> Approval | None:
        approval = await self.get_by_id(approval_id)
        if approval:
            approval.status = decision
            approval.decision_json = decision_data or {}
            approval.resolved_at = self._now()
            await self._session.flush()
        return approval


# ---------------------------------------------------------------------------
# Artifact Repository
# ---------------------------------------------------------------------------

class ArtifactRepository(BaseRepository):
    """Repository for Artifact aggregate."""

    async def create(
        self,
        artifact_id: str,
        conversation_id: str,
        run_id: str,
        artifact_type: str,
        payload: dict[str, Any],
        uri: str | None = None,
    ) -> Artifact:
        artifact = Artifact(
            id=artifact_id,
            conversation_id=conversation_id,
            run_id=run_id,
            artifact_type=artifact_type,
            uri=uri,
            payload_json=payload,
            status="pending",
        )
        self._session.add(artifact)
        await self._session.flush()
        return artifact

    async def get_by_id(self, artifact_id: str) -> Artifact | None:
        result = await self._session.execute(
            select(Artifact).where(Artifact.id == artifact_id)
        )
        return result.scalar_one_or_none()

    async def mark_ready(self, artifact_id: str, uri: str) -> Artifact | None:
        artifact = await self.get_by_id(artifact_id)
        if artifact:
            artifact.status = "ready"
            artifact.uri = uri
            await self._session.flush()
        return artifact


# ---------------------------------------------------------------------------
# Tool Execution Repository
# ---------------------------------------------------------------------------

class ToolExecutionRepository(BaseRepository):
    """Repository for ToolExecution aggregate."""

    async def create(
        self,
        tool_execution_id: str,
        conversation_id: str,
        run_id: str,
        tool_name: str,
        input_data: dict[str, Any],
    ) -> ToolExecution:
        exec_ = ToolExecution(
            id=tool_execution_id,
            conversation_id=conversation_id,
            run_id=run_id,
            tool_name=tool_name,
            input_json=input_data,
            status="pending",
            attempt=1,
        )
        self._session.add(exec_)
        await self._session.flush()
        return exec_

    async def mark_started(self, tool_execution_id: str) -> ToolExecution | None:
        exec_ = await self._session.get(ToolExecution, tool_execution_id)
        if exec_:
            exec_.status = "running"
            exec_.started_at = self._now()
            await self._session.flush()
        return exec_

    async def mark_completed(
        self, tool_execution_id: str, output: dict[str, Any]
    ) -> ToolExecution | None:
        exec_ = await self._session.get(ToolExecution, tool_execution_id)
        if exec_:
            exec_.status = "completed"
            exec_.output_json = output
            exec_.finished_at = self._now()
            await self._session.flush()
        return exec_

    async def mark_failed(
        self, tool_execution_id: str, error: str, error_code: str | None = None
    ) -> ToolExecution | None:
        exec_ = await self._session.get(ToolExecution, tool_execution_id)
        if exec_:
            exec_.status = "failed"
            exec_.error_json = {"error": error, "error_code": error_code}
            exec_.finished_at = self._now()
            await self._session.flush()
        return exec_


# ---------------------------------------------------------------------------
# Checkpoint Repository
# ---------------------------------------------------------------------------

class CheckpointRepository(BaseRepository):
    """Repository for LangGraph Checkpoint aggregate."""

    async def save(
        self,
        thread_id: str,
        checkpoint_id: str,
        state: dict[str, Any],
        parent_checkpoint_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Checkpoint:
        checkpoint = Checkpoint(
            thread_id=thread_id,
            checkpoint_id=checkpoint_id,
            parent_checkpoint_id=parent_checkpoint_id,
            state_json=state,
            metadata_json=metadata or {},
        )
        self._session.add(checkpoint)
        await self._session.flush()
        return checkpoint

    async def get_latest(self, thread_id: str) -> Checkpoint | None:
        result = await self._session.execute(
            select(Checkpoint)
            .where(Checkpoint.thread_id == thread_id)
            .order_by(desc(Checkpoint.created_at))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_by_checkpoint_id(
        self, thread_id: str, checkpoint_id: str
    ) -> Checkpoint | None:
        result = await self._session.execute(
            select(Checkpoint).where(
                Checkpoint.thread_id == thread_id,
                Checkpoint.checkpoint_id == checkpoint_id,
            )
        )
        return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# Outbox Repository
# ---------------------------------------------------------------------------

class OutboxRepository(BaseRepository):
    """Repository for OutboxEvent aggregate."""

    async def enqueue(
        self,
        aggregate_type: str,
        aggregate_id: str,
        event_type: str,
        payload: dict[str, Any],
    ) -> OutboxEvent:
        event = OutboxEvent(
            id=str(uuid4()),
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            event_type=event_type,
            payload_json=payload,
            attempt=0,
        )
        self._session.add(event)
        await self._session.flush()
        return event

    async def get_unpublished(self, limit: int = 100) -> Sequence[OutboxEvent]:
        result = await self._session.execute(
            select(OutboxEvent)
            .where(OutboxEvent.published_at.is_(None))
            .order_by(OutboxEvent.created_at)
            .limit(limit)
        )
        return result.scalars().all()

    async def mark_published(self, event_id: str) -> None:
        result = await self._session.execute(
            select(OutboxEvent).where(OutboxEvent.id == event_id)
        )
        event = result.scalar_one_or_none()
        if event:
            event.published_at = self._now()
            await self._session.flush()

    async def mark_failed(self, event_id: str, error: str) -> None:
        result = await self._session.execute(
            select(OutboxEvent).where(OutboxEvent.id == event_id)
        )
        event = result.scalar_one_or_none()
        if event:
            event.attempt += 1
            event.last_error = error
            await self._session.flush()


# ---------------------------------------------------------------------------
# Audit Log Repository
# ---------------------------------------------------------------------------


class AuditLogRepository(BaseRepository):
    """Repository for AuditLog aggregate (WP-10)."""

    async def create(
        self,
        actor_type: str,
        actor_id: str,
        action: str,
        resource_type: str,
        resource_id: str,
        payload: dict[str, Any] | None = None,
    ) -> AuditLog:
        log = AuditLog(
            id=str(uuid4()),
            actor_type=actor_type,
            actor_id=actor_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            payload_json=payload or {},
        )
        self._session.add(log)
        await self._session.flush()
        return log

    async def get_by_resource(
        self,
        resource_type: str,
        resource_id: str,
        limit: int = 50,
    ) -> Sequence[AuditLog]:
        result = await self._session.execute(
            select(AuditLog)
            .where(
                AuditLog.resource_type == resource_type,
                AuditLog.resource_id == resource_id,
            )
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()
