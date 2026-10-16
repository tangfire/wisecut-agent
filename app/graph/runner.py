"""Graph runner: executes the Agent Film StateGraph with interrupt/resume.

This is the bridge between the Worker (WP-05) and LangGraph (WP-06/WP-11).

The runner:
  1. Loads the Run and conversation from the database.
  2. Builds the LangGraph StateGraph with a PostgreSQL checkpointer.
  3. Executes the graph using ainvoke, handling node-level interrupts.
  4. When a node sets pending_interaction, the runner pauses and returns.
  5. When the user responds, the runner resumes from the checkpoint.
  6. Emits events to the database (run.started, tool.completed, etc.).
  7. Handles cancellation via the cancel flag.

Usage:
    runner = GraphRunner()
    await runner.execute_run(run_id)           # initial execution
    await runner.resume_run(run_id, response)  # resume after interaction
"""
from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any, cast

from langgraph.errors import GraphInterrupt
from langgraph.types import Command

from app.graph.builder import build_default_graph
from app.graph.profiles import get_profile
from app.graph.state import AgentFilmState, create_initial_state
from app.persistence.checkpointer import PostgreSQLCheckpointSaver
from app.persistence.engine import get_session_factory
from app.persistence.repositories import (
    EventRepository,
    InteractionRepository,
    RunRepository,
)
from app.settings import settings
from app.worker.cancel import CancelController
from app.worker.lock_manager import ConversationLock

logger = logging.getLogger(__name__)


class GraphRunner:
    """Executes a single Agent Film Run through the LangGraph StateGraph.

    The runner is called by the Worker's RunHandler after it acquires
    the conversation lock.

    WP-11: replaces the stub with actual LangGraph ainvoke execution,
    proper interrupt/resume handling, and event emission.
    """

    def __init__(
        self,
        checkpointer: Any = None,
        session_factory: Any = None,
    ) -> None:
        self._checkpointer = checkpointer
        self._session_factory = session_factory

    async def execute_run(
        self,
        run_id: str,
        conversation_id: str,
        lock: ConversationLock | None = None,
        loop: asyncio.AbstractEventLoop | None = None,
        interaction_response: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute or resume a single Run.

        Args:
            run_id: The MAA run ID.
            conversation_id: The MAA conversation ID.
            lock: The conversation lock (for heartbeat during execution).
            loop: The event loop (for scheduling DB operations).
            interaction_response: If provided, resume from an interaction
                with this response data.

        Returns:
            Dict with execution result including status and any interaction.
        """
        factory = self._session_factory or get_session_factory()

        # Keep the session open for the entire graph execution so the
        # GraphRunner can write Run/Event/Interaction records during ainvoke.
        # The checkpointer receives the factory (not the session) and creates
        # its own short sessions per call to avoid asyncpg concurrency errors.
        async with factory() as session:
            checkpointer = PostgreSQLCheckpointSaver(factory)
            run_repo = RunRepository(session)

            # Load run and conversation
            run = await run_repo.get_by_id(run_id)
            if run is None:
                logger.error("Run not found", extra={"run_id": run_id})
                return {"status": "error", "error": "run_not_found"}

            from sqlalchemy import select

            from app.persistence.models import Conversation

            execute_result = await session.execute(
                select(Conversation).where(Conversation.id == conversation_id)
            )
            conversation = execute_result.scalar_one_or_none()
            if conversation is None:
                logger.error("Conversation not found", extra={"conversation_id": conversation_id})
                return {"status": "error", "error": "conversation_not_found"}

            profile = get_profile(
                conversation.metadata_json.get("agent_profile_id", "one-click-quick")
                if conversation.metadata_json
                else "one-click-quick"
            )
            language = (conversation.metadata_json or {}).get("response_language", "zh-CN")
            graph_thread_id = run.graph_thread_id or run_id

            # Check if this is a fresh run or a resume
            if interaction_response:
                initial_state = None
                config = {"configurable": {"thread_id": graph_thread_id}}
                await self._emit_interaction_resolved(
                    session, conversation_id, run_id, interaction_response
                )
            else:
                initial_state = create_initial_state(
                    conversation_id=conversation_id,
                    run_id=run_id,
                    profile_id=profile.profile_id,
                    language=language,
                )
                config = {"configurable": {"thread_id": graph_thread_id}}

                await run_repo.mark_started(run_id)

                event_repo = EventRepository(session)
                seq = await event_repo.get_next_seq(conversation_id, run_id)
                await event_repo.create(
                    event_id=f"evt-{datetime.now(UTC).timestamp()}",
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
            await session.commit()

            # Build graph with checkpointer (checkpointer gets factory, not session)
            compiled = build_default_graph(checkpointer=checkpointer)

            # Execute graph
            try:
                if interaction_response:
                    result = await self._resume_graph(
                        compiled=compiled,
                        config=config,
                        interaction_response=interaction_response,
                        run_id=run_id,
                        conversation_id=conversation_id,
                        session=session,
                    )
                else:
                    assert initial_state is not None
                    result = await self._run_graph(
                        compiled=compiled,
                        config=config,
                        initial_state=initial_state,
                        run_id=run_id,
                        conversation_id=conversation_id,
                        lock=lock,
                        session=session,
                    )
                return result

            except GraphInterrupt as exc:
                await self._handle_interrupt(exc, run_id, conversation_id, graph_thread_id, pending_interaction=None, session=session)
                return {"status": "waiting_interaction"}

            except Exception as exc:
                logger.error(
                    "Graph execution failed",
                    extra={"run_id": run_id, "error": str(exc)},
                )
                await run_repo.mark_finished(run_id, "failed", str(exc))
                await session.commit()
                return {"status": "failed", "error": str(exc)}

    async def _run_graph(
        self,
        compiled: Any,
        config: dict[str, Any],
        initial_state: AgentFilmState,
        run_id: str,
        conversation_id: str,
        lock: ConversationLock | None = None,
        session: Any = None,
    ) -> dict[str, Any]:
        """Execute the graph from the beginning."""
        import redis.asyncio as aioredis

        redis_client = aioredis.from_url(settings.redis_url)
        cancel = CancelController(redis_client)

        try:
            if await cancel.is_cancelled(run_id):
                await self._mark_cancelled(run_id)
                return {"status": "cancelled"}

            # Use astream with stream_mode="updates" to detect __interrupt__ chunks
            state = initial_state
            interrupted = False
            async for chunk in compiled.astream(state, config, stream_mode="updates"):
                if "__interrupt__" in chunk:
                    # Graph paused for interaction
                    interrupted = True
                    # Fetch full state from the checkpointer
                    try:
                        checkpoint_tuple = await compiled.checkpointer.agetuple(  # type: ignore[attr-defined]
                            config
                        )
                        if checkpoint_tuple:
                            state = checkpoint_tuple.checkpoint.get("channel_values", state)
                    except Exception:
                        pass
                    break
                # Apply node updates to state
                for node_name, node_output in chunk.items():
                    if node_name != "__interrupt__":
                        state = {**state, **node_output}

            if interrupted:
                # Commit checkpoints before interrupt
                if session is not None:
                    await session.commit()

                # Extract pending_interaction from state
                pending_interaction = state.get("pending_interaction")

                await self._handle_interrupt(
                    exc=None,
                    run_id=run_id,
                    conversation_id=conversation_id,
                    thread_id=config["configurable"]["thread_id"],
                    pending_interaction=pending_interaction,
                    session=session,
                )
                return {"status": "waiting_interaction"}

            # Commit checkpoints written during graph execution
            if session is not None:
                await session.commit()

            # Graph completed normally
            assert session is not None
            await self._handle_completion(run_id, conversation_id, cast(dict[str, Any], state), session=session)
            return {"status": "completed", "result": state}

        except GraphInterrupt as exc:
            # Fallback for LangGraph versions that raise GraphInterrupt
            if session is not None:
                await session.commit()
            await self._handle_interrupt(exc, run_id, conversation_id, config["configurable"]["thread_id"], session=session)
            return {"status": "waiting_interaction"}

        finally:
            try:
                await redis_client.close()
            except Exception:
                pass

    async def _resume_graph(
        self,
        compiled: Any,
        config: dict[str, Any],
        interaction_response: dict[str, Any],
        run_id: str,
        conversation_id: str,
        session: Any = None,
    ) -> dict[str, Any]:
        """Resume the graph from an interaction response."""
        import redis.asyncio as aioredis

        redis_client = aioredis.from_url(settings.redis_url)
        cancel = CancelController(redis_client)

        try:
            if await cancel.is_cancelled(run_id):
                await self._mark_cancelled(run_id)
                return {"status": "cancelled"}

            # Use astream with stream_mode="updates" to detect __interrupt__ chunks
            state: dict[str, Any] = {}
            interrupted = False
            resume_input = Command(resume=interaction_response)  # type: ignore[var-annotated]
            async for chunk in compiled.astream(resume_input, config, stream_mode="updates"):
                if "__interrupt__" in chunk:
                    # Graph paused for interaction again
                    interrupted = True
                    try:
                        checkpoint_tuple = await compiled.checkpointer.agetuple(  # type: ignore[attr-defined]
                            config
                        )
                        if checkpoint_tuple:
                            state = checkpoint_tuple.checkpoint.get("channel_values", state)
                    except Exception:
                        pass
                    break
                for node_name, node_output in chunk.items():
                    if node_name != "__interrupt__":
                        state = {**state, **node_output}

            if interrupted:
                # Commit checkpoints before interrupt
                if session is not None:
                    await session.commit()

                pending_interaction = state.get("pending_interaction")
                await self._handle_interrupt(
                    exc=None,
                    run_id=run_id,
                    conversation_id=conversation_id,
                    thread_id=config["configurable"]["thread_id"],
                    pending_interaction=pending_interaction,
                    session=session,
                )
                return {"status": "waiting_interaction"}

            # Commit checkpoints written during graph execution
            if session is not None:
                await session.commit()

            assert session is not None
            await self._handle_completion(run_id, conversation_id, state, session=session)
            return {"status": "completed", "result": state}

        except GraphInterrupt as exc:
            # Fallback for LangGraph versions that raise GraphInterrupt
            if session is not None:
                await session.commit()
            await self._handle_interrupt(exc, run_id, conversation_id, config["configurable"]["thread_id"], session=session)
            return {"status": "waiting_interaction"}
        finally:
            try:
                await redis_client.close()
            except Exception:
                pass

    async def _handle_interrupt(
        self,
        exc: GraphInterrupt | None,
        run_id: str,
        conversation_id: str,
        thread_id: str,
        pending_interaction: dict[str, Any] | None = None,
        session: Any = None,
    ) -> None:
        """Handle a graph interrupt: update run status and emit interaction event."""
        from uuid import uuid4

        interaction_id = f"int-{uuid4().hex[:12]}"
        checkpoint_id = ""

        # Fetch checkpoint_id from checkpointer using a short session
        try:
            factory = self._session_factory or get_session_factory()
            cp = PostgreSQLCheckpointSaver(factory)
            checkpoint_tuple = await cp.aget_tuple(
                {"configurable": {"thread_id": thread_id}}
            )
            if checkpoint_tuple:
                checkpoint_id = checkpoint_tuple.checkpoint.get("id", "")
        except Exception:
            pass

        # Use provided session or create a new one
        if session is not None:
            run_repo = RunRepository(session)
            await run_repo.mark_waiting_interaction(run_id)

            # Create Interaction record and emit event if pending_interaction is set
            if pending_interaction:
                from app.persistence.models import Interaction

                interaction = Interaction(
                    id=interaction_id,
                    conversation_id=conversation_id,
                    run_id=run_id,
                    intent=pending_interaction.get("intent", "product_context_review"),
                    payload_json=pending_interaction,
                    status="pending",
                )
                session.add(interaction)

                event_repo = EventRepository(session)
                event_id = f"evt-{datetime.now(UTC).timestamp()}"
                await event_repo.create(
                    event_id=event_id,
                    conversation_id=conversation_id,
                    run_id=run_id,
                    seq=await event_repo.get_next_seq(conversation_id, run_id),
                    event_type="interaction.requested",
                    payload={
                        "interaction_id": interaction_id,
                        "interaction_type": pending_interaction.get("intent", "product_context_review"),
                        "action": "confirm",
                        "card_type": pending_interaction.get("intent", "confirm_extracted_product_context"),
                        "data": pending_interaction,
                        "checkpoint_id": checkpoint_id,
                        "created_at": datetime.now(UTC).isoformat(),
                    },
                )
        else:
            factory = get_session_factory()
            async with factory() as session:
                run_repo = RunRepository(session)
                await run_repo.mark_waiting_interaction(run_id)

                if pending_interaction:
                    from app.persistence.models import Interaction

                    interaction = Interaction(
                        id=interaction_id,
                        conversation_id=conversation_id,
                        run_id=run_id,
                        intent=pending_interaction.get("intent", "product_context_review"),
                        payload_json=pending_interaction,
                        status="pending",
                    )
                    session.add(interaction)

                    event_repo = EventRepository(session)
                    event_id = f"evt-{datetime.now(UTC).timestamp()}"
                    await event_repo.create(
                        event_id=event_id,
                        conversation_id=conversation_id,
                        run_id=run_id,
                        seq=await event_repo.get_next_seq(conversation_id, run_id),
                        event_type="interaction.requested",
                        payload={
                            "interaction_id": interaction_id,
                            "interaction_type": pending_interaction.get("intent", "product_context_review"),
                            "action": "confirm",
                            "card_type": pending_interaction.get("intent", "confirm_extracted_product_context"),
                            "data": pending_interaction,
                            "checkpoint_id": checkpoint_id,
                            "created_at": datetime.now(UTC).isoformat(),
                        },
                    )

        logger.info(
            "Run paused for interaction",
            extra={"run_id": run_id, "thread_id": thread_id, "has_interaction": bool(pending_interaction)},
        )

    async def _handle_completion(
        self,
        run_id: str,
        conversation_id: str,
        result: dict[str, Any],
        session: Any = None,
    ) -> None:
        """Handle graph completion: mark run finished and emit terminal event.

        Uses the provided session when available to avoid opening a second
        connection; falls back to creating its own session when called
        from paths that don't hold one.
        """
        run_repo: RunRepository
        event_repo: EventRepository

        if session is not None:
            run_repo = RunRepository(session)
            event_repo = EventRepository(session)
        else:
            factory = get_session_factory()
            async with factory() as session:
                return await self._handle_completion(run_id, conversation_id, result, session=session)

        # Determine final status
        errors = result.get("errors", []) if isinstance(result, dict) else []
        status = "completed"
        error_msg = None
        if errors:
            fatal = [e for e in errors if e.get("fatal")]
            if fatal:
                status = "failed"
                error_msg = fatal[0].get("error", "fatal error")

        await run_repo.mark_finished(run_id, status, error_msg)

        # Emit terminal event
        seq = await event_repo.get_next_seq(conversation_id, run_id)
        terminal_type = {
            "completed": "run.completed",
            "failed": "run.failed",
            "cancelled": "run.cancelled",
        }.get(status, "run.failed")
        await event_repo.create(
            event_id=f"evt-{datetime.now(UTC).timestamp()}",
            conversation_id=conversation_id,
            run_id=run_id,
            seq=seq,
            event_type=terminal_type,
            payload={
                "run_id": run_id,
                "conversation_id": conversation_id,
                "status": status,
                "finished_at": datetime.now(UTC).isoformat(),
            },
        )

    async def _mark_cancelled(self, run_id: str) -> None:
        """Mark a run as cancelled."""
        factory = get_session_factory()
        async with factory() as session:
            run_repo = RunRepository(session)
            await run_repo.mark_finished(run_id, "cancelled", "cancelled_by_user")
            await session.commit()

    async def _emit_interaction_resolved(
        self,
        session: Any,
        conversation_id: str,
        run_id: str,
        response: dict[str, Any],
    ) -> None:
        """Emit interaction.resolved event."""
        event_repo = EventRepository(session)
        interaction_repo = InteractionRepository(session)

        interaction_id = response.get("interaction_id", "")
        seq = await event_repo.get_next_seq(conversation_id, run_id)

        await event_repo.create(
            event_id=f"evt-{datetime.now(UTC).timestamp()}",
            conversation_id=conversation_id,
            run_id=run_id,
            seq=seq,
            event_type="interaction.resolved",
            payload={
                "interaction_id": interaction_id,
                "action": response.get("action", "approve"),
                "content": response.get("content", {}),
                "resolved_at": datetime.now(UTC).isoformat(),
            },
        )

        if interaction_id:
            await interaction_repo.resolve(
                interaction_id=interaction_id,
                action=response.get("action", "approve"),
                answer=response.get("content", {}),
            )
