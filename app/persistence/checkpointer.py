"""LangGraph Checkpoint Saver backed by PostgreSQL.

Implements the LangGraph CheckpointSaver interface using our Checkpoint model.
Maps LangGraph thread_id <-> run.graph_thread_id per plan.md section 5.3.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from langgraph.checkpoint.base import (
    BaseCheckpointSaver,
    Checkpoint,
    CheckpointTuple,
)
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.models import Checkpoint as CheckpointModel
from app.persistence.repositories import CheckpointRepository


class PostgreSQLCheckpointSaver(BaseCheckpointSaver[Any]):
    """PostgreSQL-backed checkpoint saver for LangGraph.

    Stores each checkpoint as a row in the `checkpoint` table.
    The `thread_id` column maps to `run.graph_thread_id`.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = CheckpointRepository(session)

    def _extract_thread_id(self, config: dict[str, Any]) -> str:
        """Extract thread_id from a RunnableConfig."""
        return config.get("configurable", {}).get("thread_id", "")

    def _extract_checkpoint_id(self, config: dict[str, Any]) -> str | None:
        """Extract checkpoint_id from a RunnableConfig."""
        return config.get("configurable", {}).get("checkpoint_id")

    async def aget(
        self,
        config: dict[str, Any],
    ) -> Checkpoint | None:
        """Get a checkpoint by config."""
        thread_id = self._extract_thread_id(config)
        checkpoint_id = self._extract_checkpoint_id(config)
        if not thread_id:
            return None
        if checkpoint_id:
            model = await self._repo.get_by_checkpoint_id(thread_id, checkpoint_id)
        else:
            model = await self._repo.get_latest(thread_id)
        if model is None:
            return None
        return self._model_to_checkpoint(model)

    async def aget_tuple(
        self,
        config: dict[str, Any],
    ) -> CheckpointTuple | None:
        """Get a checkpoint tuple asynchronously."""
        thread_id = self._extract_thread_id(config)
        if not thread_id:
            return None
        model = await self._repo.get_latest(thread_id)
        if model is None:
            return None
        checkpoint = self._model_to_checkpoint(model)
        parent_config = None
        if model.parent_checkpoint_id:
            parent_config = {
                "configurable": {
                    "thread_id": thread_id,
                    "checkpoint_id": model.parent_checkpoint_id,
                }
            }
        return CheckpointTuple(
            config={"configurable": {"thread_id": thread_id, "checkpoint_id": model.checkpoint_id}},
            checkpoint=checkpoint,
            metadata=checkpoint.metadata,
            parent_config=parent_config,
        )

    def get_tuple(self, config: dict[str, Any]) -> CheckpointTuple | None:
        """Get a checkpoint tuple (sync - not implemented for async saver)."""
        raise NotImplementedError("Use aget_tuple for async checkpointer")

    async def aput(
        self,
        config: dict[str, Any],
        checkpoint: Checkpoint,
        metadata: dict[str, Any],
        new_versions: dict[str, Any],
    ) -> dict[str, Any]:
        """Save a checkpoint."""
        thread_id = self._extract_thread_id(config)
        # Use checkpoint_id from config if provided (LangGraph generates stable IDs)
        checkpoint_id = self._extract_checkpoint_id(config)
        if not checkpoint_id:
            checkpoint_id = str(__import__("uuid").uuid4())
        parent_id = (metadata or {}).get("parent_checkpoint_id")
        state = dict(checkpoint.get("channel_values", {}))

        try:
            await self._repo.save(
                thread_id=thread_id,
                checkpoint_id=checkpoint_id,
                state=state,
                parent_checkpoint_id=parent_id,
                metadata=metadata,
            )
        except Exception:
            # If checkpoint already exists (e.g., retry within same session),
            # rollback the failed insert and update instead
            try:
                await self._session.rollback()
            except Exception:
                pass
            from sqlalchemy import update
            await self._session.execute(
                update(CheckpointModel)
                .where(
                    CheckpointModel.thread_id == thread_id,
                    CheckpointModel.checkpoint_id == checkpoint_id,
                )
                .values(state_json=state, metadata_json=metadata)
            )
        return {"configurable": {"thread_id": thread_id, "checkpoint_id": checkpoint_id}}

    async def aput_multi(
        self,
        configs: list[dict[str, Any]],
        checkpoints: list[Checkpoint],
        metadata_list: list[dict[str, Any]],
        new_versions: dict[str, Any],
    ) -> dict[str, Any]:
        """Save multiple checkpoints."""
        result = {}
        for config, checkpoint, metadata in zip(configs, checkpoints, metadata_list):
            res = await self.aput(config, checkpoint, metadata, new_versions)
            result.update(res)
        return result

    async def aput_writes(
        self,
        config: dict[str, Any],
        writes: list[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        """Store intermediate writes linked to a checkpoint."""
        thread_id = self._extract_thread_id(config)
        if not thread_id:
            return
        model = await self._repo.get_latest(thread_id)
        if model is None:
            return
        state = model.state_json or {}
        for channel, value in writes:
            state[channel] = value
        # Update the existing checkpoint directly to avoid INSERT conflicts
        from sqlalchemy import update
        await self._session.execute(
            update(CheckpointModel)
            .where(
                CheckpointModel.thread_id == thread_id,
                CheckpointModel.checkpoint_id == model.checkpoint_id,
            )
            .values(state_json=state)
        )

    async def alist(
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
        query = (
            select(CheckpointModel)
            .where(CheckpointModel.thread_id == thread_id)
            .order_by(desc(CheckpointModel.created_at))
        )
        if limit:
            query = query.limit(limit)
        result = await self._session.execute(query)
        models = result.scalars().all()
        for model in models:
            checkpoint = self._model_to_checkpoint(model)
            yield CheckpointTuple(
                config={"configurable": {"thread_id": thread_id, "checkpoint_id": model.checkpoint_id}},
                checkpoint=checkpoint,
                metadata=checkpoint.metadata,
            )

    async def adelete(self, config: dict[str, Any]) -> None:
        """Delete a checkpoint."""
        thread_id = self._extract_thread_id(config)
        checkpoint_id = self._extract_checkpoint_id(config)
        if not thread_id or not checkpoint_id:
            return
        from sqlalchemy import delete
        await self._session.execute(
            delete(CheckpointModel).where(
                CheckpointModel.thread_id == thread_id,
                CheckpointModel.checkpoint_id == checkpoint_id,
            )
        )
        await self._session.flush()

    async def aexists(self, config: dict[str, Any]) -> bool:
        """Check if a checkpoint exists."""
        thread_id = self._extract_thread_id(config)
        checkpoint_id = self._extract_checkpoint_id(config)
        if not thread_id or not checkpoint_id:
            return False
        model = await self._repo.get_by_checkpoint_id(thread_id, checkpoint_id)
        return model is not None

    @staticmethod
    def _model_to_checkpoint(model: CheckpointModel) -> Checkpoint:
        """Convert a Checkpoint model to a LangGraph Checkpoint."""
        state = model.state_json or {}
        return Checkpoint(  # type: ignore[typeddict-item]
            channel_values=state.get("channel_values", state),
            metadata=model.metadata_json or {},
            id=model.checkpoint_id,
            v=1,
            ts=model.created_at.isoformat() if model.created_at else "",
            channel_versions=state.get("channel_versions", {}),
            versions_seen=state.get("versions_seen", {}),
            updated_channels=state.get("updated_channels"),
        )
