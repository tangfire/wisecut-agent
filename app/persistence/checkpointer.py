"""LangGraph Checkpoint Saver backed by PostgreSQL.

Implements the LangGraph CheckpointSaver interface using our Checkpoint model.
Maps LangGraph thread_id <-> run.graph_thread_id per plan.md section 5.3.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, cast

from langchain_core.runnables.config import RunnableConfig
from langgraph.checkpoint.base import (
    BaseCheckpointSaver,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
)
from sqlalchemy import desc, insert, select

from app.persistence.models import Checkpoint as CheckpointModel
from app.persistence.repositories import CheckpointRepository


class PostgreSQLCheckpointSaver(BaseCheckpointSaver[Any]):
    """PostgreSQL-backed checkpoint saver for LangGraph.

    Stores each checkpoint as a row in the `checkpoint` table.
    The `thread_id` column maps to `run.graph_thread_id`.

    Session isolation (WP-11): each aget/aput/aput_writes/alist method
    creates its own short-lived AsyncSession via the injected factory.
    This prevents the checkpointer from sharing a session with the
    GraphRunner business session, eliminating the
    "asyncpg InterfaceError: another operation is in progress" error
    that occurs when LangGraph calls aput/aput_writes concurrently
    during ainvoke while the GraphRunner holds the same session.
    """

    def __init__(self, session_factory: Any) -> None:
        self._session_factory = session_factory

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _extract_thread_id(self, config: dict[str, Any]) -> str:
        """Extract thread_id from a RunnableConfig."""
        return cast(str, config.get("configurable", {}).get("thread_id", ""))

    def _extract_checkpoint_id(self, config: dict[str, Any]) -> str | None:
        """Extract checkpoint_id from a RunnableConfig."""
        return cast(str | None, config.get("configurable", {}).get("checkpoint_id"))

    @staticmethod
    def _model_to_checkpoint(model: CheckpointModel) -> Checkpoint:
        """Convert a Checkpoint model to a LangGraph Checkpoint."""
        state = model.state_json or {}

        # LangGraph checkpoints may have channel_values nested or at top level
        # Try channel_values first, then reconstruct from top-level keys
        if "channel_values" in state and isinstance(state["channel_values"], dict):
            channel_values = dict(state["channel_values"])
            # Top-level keys override channel_values (LangGraph stores updates at top level)
            typ_keys = {"v", "id", "ts", "channel_values", "channel_versions", "versions_seen", "updated_channels", "pending_sends"}
            for key, value in state.items():
                if key not in typ_keys:
                    channel_values[key] = value
        else:
            channel_values = dict(state)

        # Build the checkpoint dict with all required LangGraph fields
        # Note: pending_sends is not in the Checkpoint TypedDict but is required
        # by LangGraph 0.2.x internal code (pregel/algo.py accesses checkpoint["pending_sends"])
        checkpoint: Checkpoint = {
            "channel_values": channel_values,
            "id": model.checkpoint_id,
            "v": 1,
            "ts": model.created_at.isoformat() if model.created_at else "",
            "channel_versions": state.get("channel_versions", {}),
            "versions_seen": state.get("versions_seen", {}),
            "updated_channels": state.get("updated_channels"),
        }
        # Add pending_sends if present (required by LangGraph 0.2.x)
        if "pending_sends" in state:
            checkpoint["pending_sends"] = state["pending_sends"]  # type: ignore[typeddict-unknown-key]
        return checkpoint

    # ------------------------------------------------------------------
    # CheckpointSaver interface — each method owns its own session
    # ------------------------------------------------------------------

    async def aget(  # type: ignore[override]
        self,
        config: dict[str, Any],
    ) -> Checkpoint | None:
        """Get a checkpoint by config."""
        thread_id = self._extract_thread_id(config)
        checkpoint_id = self._extract_checkpoint_id(config)
        if not thread_id:
            return None
        async with self._session_factory() as session:
            repo = CheckpointRepository(session)
            if checkpoint_id:
                model = await repo.get_by_checkpoint_id(thread_id, checkpoint_id)
            else:
                model = await repo.get_latest(thread_id)
        if model is None:
            return None
        return self._model_to_checkpoint(model)

    async def aget_tuple(  # type: ignore[override]
        self,
        config: dict[str, Any],
    ) -> CheckpointTuple | None:
        """Get a checkpoint tuple asynchronously."""
        thread_id = self._extract_thread_id(config)
        if not thread_id:
            return None
        async with self._session_factory() as session:
            repo = CheckpointRepository(session)
            model = await repo.get_latest(thread_id)
        if model is None:
            return None
        checkpoint = self._model_to_checkpoint(model)
        # Construct CheckpointMetadata from stored metadata_json
        model_metadata = model.metadata_json or {}
        checkpoint_metadata = cast(
            CheckpointMetadata,
            {
                "source": model_metadata.get("source", "loop"),
                "step": model_metadata.get("step", 1),
                "parents": model_metadata.get("parents", {}),
            },
        )
        parent_config = None
        if model.parent_checkpoint_id:
            parent_config = cast(
                RunnableConfig,
                {
                    "configurable": {
                        "thread_id": thread_id,
                        "checkpoint_id": model.parent_checkpoint_id,
                    }
                },
            )
        return CheckpointTuple(
            config=cast(RunnableConfig, {"configurable": {"thread_id": thread_id, "checkpoint_id": model.checkpoint_id}}),
            checkpoint=checkpoint,
            metadata=checkpoint_metadata,
            parent_config=parent_config,
        )

    def get_tuple(self, config: dict[str, Any]) -> CheckpointTuple | None:  # type: ignore[override]
        """Get a checkpoint tuple (sync - not implemented for async saver)."""
        raise NotImplementedError("Use aget_tuple for async checkpointer")

    async def aput(  # type: ignore[override]
        self,
        config: dict[str, Any],
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata | dict[str, Any],
        new_versions: dict[str, Any],
    ) -> RunnableConfig:
        """Save a checkpoint using PostgreSQL upsert.

        Uses INSERT ... ON CONFLICT DO UPDATE so concurrent calls with the
        same (thread_id, checkpoint_id) do not raise IntegrityError.
        Each call gets its own short session/transaction.
        """
        thread_id = self._extract_thread_id(config)
        # Use checkpoint_id from config if provided (LangGraph generates stable IDs)
        checkpoint_id = self._extract_checkpoint_id(config)
        if not checkpoint_id:
            checkpoint_id = str(__import__("uuid").uuid4())
        parent_id = (metadata.get("parents", {}) if isinstance(metadata, dict) else {}).get("parent_checkpoint_id")
        # Save the entire checkpoint dict to preserve all LangGraph internal keys
        # (pending_sends, channel_versions, versions_seen, updated_channels, etc.)
        state = dict(checkpoint)
        meta = cast(dict[str, Any], metadata)

        async with self._session_factory() as session:
            stmt = (
                insert(CheckpointModel)
                .values(
                    thread_id=thread_id,
                    checkpoint_id=checkpoint_id,
                    parent_checkpoint_id=parent_id,
                    state_json=state,
                    metadata_json=meta,
                )
                .on_conflict_do_update(  # type: ignore[attr-defined]
                    constraint="checkpoint_pkey",
                    set_={
                        "state_json": state,
                        "metadata_json": meta,
                    },
                )
            )
            await session.execute(stmt)
            await session.commit()

        return cast(RunnableConfig, {"configurable": {"thread_id": thread_id, "checkpoint_id": checkpoint_id}})

    async def aput_multi(
        self,
        configs: list[dict[str, Any]],
        checkpoints: list[Checkpoint],
        metadata_list: list[dict[str, Any]],
        new_versions: dict[str, Any],
    ) -> dict[str, Any]:
        """Save multiple checkpoints."""
        result: dict[str, Any] = {}
        for config, checkpoint, metadata in zip(configs, checkpoints, metadata_list):
            res = await self.aput(config, checkpoint, metadata, new_versions)
            result.update(res)
        return result

    async def aput_writes(  # type: ignore[override]
        self,
        config: dict[str, Any],
        writes: list[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        """Store intermediate writes linked to a checkpoint.

        Reads the latest checkpoint for the thread, merges writes into its
        state, then upserts the row. Each call gets its own short session.
        """
        thread_id = self._extract_thread_id(config)
        if not thread_id:
            return

        async with self._session_factory() as session:
            repo = CheckpointRepository(session)
            model = await repo.get_latest(thread_id)
            if model is None:
                return

            state = dict(model.state_json or {})
            for channel, value in writes:
                state[channel] = value

            stmt = (
                insert(CheckpointModel)
                .values(
                    thread_id=model.thread_id,
                    checkpoint_id=model.checkpoint_id,
                    parent_checkpoint_id=model.parent_checkpoint_id,
                    state_json=state,
                    metadata_json=model.metadata_json or {},
                )
                .on_conflict_do_update(  # type: ignore[attr-defined]
                    constraint="checkpoint_pkey",
                    set_={"state_json": state},
                )
            )
            await session.execute(stmt)
            await session.commit()

    async def alist(  # type: ignore[override]
        self,
        config: dict[str, Any] | None = None,
        *,
        filter: dict[str, Any] | None = None,
        before: dict[str, Any] | None = None,
        limit: int | None = None,
    ) -> AsyncIterator[CheckpointTuple]:
        """List checkpoints for a thread."""
        if config is None:
            return
        thread_id = self._extract_thread_id(config)
        if not thread_id:
            return
        async with self._session_factory() as session:
            query = (
                select(CheckpointModel)
                .where(CheckpointModel.thread_id == thread_id)
                .order_by(desc(CheckpointModel.created_at))
            )
            if limit:
                query = query.limit(limit)
            result = await session.execute(query)
            models = result.scalars().all()
            for model in models:
                checkpoint = self._model_to_checkpoint(model)
                model_metadata = model.metadata_json or {}
                checkpoint_metadata = cast(
                    CheckpointMetadata,
                    {
                        "source": model_metadata.get("source", "loop"),
                        "step": model_metadata.get("step", 1),
                        "parents": model_metadata.get("parents", {}),
                    },
                )
                yield CheckpointTuple(
                    config=cast(RunnableConfig, {"configurable": {"thread_id": thread_id, "checkpoint_id": model.checkpoint_id}}),
                    checkpoint=checkpoint,
                    metadata=checkpoint_metadata,
                )

    async def adelete(self, config: dict[str, Any]) -> None:
        """Delete a checkpoint."""
        thread_id = self._extract_thread_id(config)
        checkpoint_id = self._extract_checkpoint_id(config)
        if not thread_id or not checkpoint_id:
            return
        async with self._session_factory() as session:
            from sqlalchemy import delete
            await session.execute(
                delete(CheckpointModel).where(
                    CheckpointModel.thread_id == thread_id,
                    CheckpointModel.checkpoint_id == checkpoint_id,
                )
            )
            await session.commit()

    async def aexists(self, config: dict[str, Any]) -> bool:
        """Check if a checkpoint exists."""
        thread_id = self._extract_thread_id(config)
        checkpoint_id = self._extract_checkpoint_id(config)
        if not thread_id or not checkpoint_id:
            return False
        async with self._session_factory() as session:
            repo = CheckpointRepository(session)
            model = await repo.get_by_checkpoint_id(thread_id, checkpoint_id)
        return model is not None
