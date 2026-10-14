"""Graph runner: executes the Agent Film StateGraph.

This is the bridge between the Worker (WP-05) and LangGraph (WP-06).

The runner:
  1. Loads the Run and conversation from the database.
  2. Builds or loads the LangGraph checkpoint.
  3. Executes the graph with interrupt/resume support.
  4. Emits events to the database (run.started, tool.completed, etc.).
  5. Handles cancellation via the cancel flag.

Usage:
    runner = GraphRunner()
    await runner.execute_run(run_id)
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from app.graph.builder import build_default_graph
from app.graph.state import AgentFilmState, create_initial_state
from app.graph.profiles import get_profile
from app.persistence.engine import get_session_factory
from app.persistence.repositories import RunRepository, EventRepository, MessageRepository
from app.worker.cancel import CancelController
from app.worker.lock_manager import ConversationLock
from app.protocol.sse import encode_sse_event, is_terminal_event

logger = logging.getLogger(__name__)


class GraphRunner:
    """Executes a single Agent Film Run through the LangGraph StateGraph.

    The runner is called by the Worker's RunHandler after it acquires
    the conversation lock.
    """

    def __init__(self, checkpointer: Any = None) -> None:
        self._checkpointer = checkpointer

    async def execute_run(
        self,
        run_id: str,
        conversation_id: str,
        lock: Optional[ConversationLock] = None,
        loop: Optional[asyncio.AbstractEventLoop] = None,
    ) -> None:
        """Execute a single Run.

        Args:
            run_id: The MAA run ID.
            conversation_id: The MAA conversation ID.
            lock: The conversation lock (for heartbeat during execution).
            loop: The event loop (for scheduling DB operations).
        """
        # Load run from database
        factory = get_session_factory()
        async with factory() as session:
            run_repo = RunRepository(session)
            run = await run_repo.get_by_id(run_id)
            if run is None:
                logger.error("Run not found", extra={"run_id": run_id})
                return

            # Load conversation
            conv_repo = session.__class__  # We'll use the session directly
            from sqlalchemy import select
            from app.persistence.models import Conversation
            result = await session.execute(
                select(Conversation).where(Conversation.id == conversation_id)
            )
            conversation = result.scalar_one_or_none()
            if conversation is None:
                logger.error("Conversation not found", extra={"conversation_id": conversation_id})
                return

            profile = get_profile(conversation.metadata_json.get("agent_profile_id") if conversation.metadata_json else None)
            language = (conversation.metadata_json or {}).get("response_language", "zh-CN")

            # Build initial state
            initial_state = create_initial_state(
                conversation_id=conversation_id,
                run_id=run_id,
                profile_id=profile.profile_id,
                language=language,
            )

            # Mark run as running
            await run_repo.mark_started(run_id)

            # Emit run.started event
            event_repo = EventRepository(session)
            seq = await event_repo.get_next_seq(conversation_id, run_id)
            await event_repo.create(
                event_id=f"evt-{datetime.now(timezone.utc).timestamp()}",
                conversation_id=conversation_id,
                run_id=run_id,
                seq=seq,
                event_type="run.started",
                payload={
                    "run_id": run_id,
                    "conversation_id": conversation_id,
                    "status": "running",
                    "phase": "starting",
                    "started_at": datetime.now(timezone.utc).isoformat(),
                },
            )
            await session.commit()

        # Build and execute graph
        graph = build_default_graph(checkpointer=self._checkpointer)

        try:
            await self._execute_graph(
                graph=graph,
                run_id=run_id,
                conversation_id=conversation_id,
                initial_state=initial_state,
                lock=lock,
                loop=loop,
            )
        except Exception as exc:
            logger.error(
                "Graph execution failed",
                extra={"run_id": run_id, "error": str(exc)},
            )
            async with factory() as session:
                run_repo = RunRepository(session)
                await run_repo.mark_finished(run_id, "failed", str(exc))
                await session.commit()

    async def _execute_graph(
        self,
        graph: Any,
        run_id: str,
        conversation_id: str,
        initial_state: AgentFilmState,
        lock: Optional[ConversationLock],
        loop: Optional[asyncio.AbstractEventLoop],
    ) -> None:
        """Execute the graph with interrupt/resume support.

        This is a stub implementation.  WP-06 will implement the full
        execution loop with proper interrupt handling.
        """
        logger.info(
            "Executing graph (stub)",
            extra={"run_id": run_id, "conversation_id": conversation_id},
        )

        # Stub: just mark as waiting_interaction for now
        # WP-06 will replace this with actual graph execution
        factory = get_session_factory()
        async with factory() as session:
            run_repo = RunRepository(session)
            await run_repo.mark_waiting_interaction(run_id)
            await session.commit()

        logger.info(
            "Graph execution paused (stub)",
            extra={"run_id": run_id},
        )
