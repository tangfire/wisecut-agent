"""LangGraph Checkpoint Saver backed by PostgreSQL.

Implements the LangGraph CheckpointSaver interface using our Checkpoint model.
Maps LangGraph thread_id <-> run.graph_thread_id per plan.md section 5.3.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any
from uuid import uuid4

from langgraph.checkpoint.base import BaseCheckpointSaver, Checkpoint
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

    async def aget(  # type: ignore[override]
        self,
        thread_id: str,
        checkpoint_id: str | None = None,
        checkpoint_map: dict[str, Any] | None = None,
    ) -> Checkpoint | None:
        """Get a checkpoint by thread_id and optional checkpoint_id."""
        if checkpoint_id:
            model = await self._repo.get_by_checkpoint_id(thread_id, checkpoint_id)
        else:
            model = await self._repo.get_latest(thread_id)

        if model is None:
            return None

        return self._model_to_checkpoint(model)

    async def aget_multi(
        self,
        thread_ids: Sequence[str],
        checkpoint_ids: Sequence[str | None] | None = None,
        checkpoint_map: dict[str, Any] | None = None,
    ) -> Sequence[Checkpoint | None]:
        """Get multiple checkpoints."""
        results = []
        for i, thread_id in enumerate(thread_ids):
            checkpoint_id = checkpoint_ids[i] if checkpoint_ids and i < len(checkpoint_ids) else None
            result = await self.aget(thread_id, checkpoint_id)
            results.append(result)
        return results

    async def aput(  # type: ignore[override]
        self,
        thread_id: str,
        checkpoint: Checkpoint,
        mapper: dict[str, Any] | None = None,
    ) -> None:
        """Save a checkpoint."""
        checkpoint_id = checkpoint.config.get("checkpoint_id") or str(uuid4())  # type: ignore[attr-defined]
        parent_id = checkpoint.parent_checkpoint_id  # type: ignore[attr-defined]

        await self._repo.save(
            thread_id=thread_id,
            checkpoint_id=checkpoint_id,
            state=checkpoint.values,
            parent_checkpoint_id=parent_id,
            metadata=checkpoint.metadata,  # type: ignore[attr-defined]
        )

    async def aput_multi(
        self,
        thread_ids: Sequence[str],
        checkpoints: Sequence[Checkpoint],
        mapper: dict[str, Any] | None = None,
    ) -> None:
        """Save multiple checkpoints."""
        for thread_id, checkpoint in zip(thread_ids, checkpoints):
            await self.aput(thread_id, checkpoint, mapper)

    async def adelete(self, thread_id: str, checkpoint_id: str) -> None:
        """Delete a checkpoint."""
        from sqlalchemy import delete
        await self._session.execute(
            delete(CheckpointModel).where(
                CheckpointModel.thread_id == thread_id,
                CheckpointModel.checkpoint_id == checkpoint_id,
            )
        )
        await self._session.flush()

    async def aexists(self, thread_id: str, checkpoint_id: str) -> bool:
        """Check if a checkpoint exists."""
        model = await self._repo.get_by_checkpoint_id(thread_id, checkpoint_id)
        return model is not None

    async def alist(  # type: ignore[override]
        self,
        thread_id: str,
        before: str | None = None,
        limit: int = 10,
    ) -> Sequence[Checkpoint]:
        """List checkpoints for a thread, optionally before a given checkpoint_id."""
        query = (
            select(CheckpointModel)
            .where(CheckpointModel.thread_id == thread_id)
            .order_by(desc(CheckpointModel.created_at))
            .limit(limit)
        )
        result = await self._session.execute(query)
        models = result.scalars().all()
        return [self._model_to_checkpoint(m) for m in models]

    @staticmethod
    def _model_to_checkpoint(model: CheckpointModel) -> Checkpoint:
        """Convert a Checkpoint model to a LangGraph Checkpoint."""
        return Checkpoint(  # type: ignore[typeddict-item]
            values=model.state_json,
            metadata=model.metadata_json or {},
            config={"checkpoint_id": model.checkpoint_id},
            parent_checkpoint_id=model.parent_checkpoint_id,
        )
