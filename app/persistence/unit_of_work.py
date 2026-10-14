"""Unit of Work pattern for transactional boundaries.

The Unit of Work coordinates repository operations within a single database
transaction, ensuring all-or-nothing semantics for business operations.

Usage:
    async with unit_of_work() as uow:
        conv = await uow.conversations.create(...)
        run = await uow.runs.create(...)
        # Both are committed when the context exits successfully.
        # If an exception is raised, both are rolled back.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.engine import get_session_factory
from app.persistence.repositories import (
    ApprovalRepository,
    ArtifactRepository,
    AuditLogRepository,
    CheckpointRepository,
    ConversationRepository,
    EventRepository,
    InteractionRepository,
    MessageRepository,
    OutboxRepository,
    RunRepository,
    ToolExecutionRepository,
)


class UnitOfWork:
    """Coordinates repository operations within a single transaction.

    All repositories share the same session, so changes are visible across
    repositories within the same UoW scope.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self.conversations = ConversationRepository(session)
        self.runs = RunRepository(session)
        self.messages = MessageRepository(session)
        self.events = EventRepository(session)
        self.interactions = InteractionRepository(session)
        self.approvals = ApprovalRepository(session)
        self.artifacts = ArtifactRepository(session)
        self.tool_executions = ToolExecutionRepository(session)
        self.checkpoints = CheckpointRepository(session)
        self.outbox = OutboxRepository(session)
        self.audit_log = AuditLogRepository(session)

    async def commit(self) -> None:
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()

    async def flush(self) -> None:
        await self._session.flush()

    @property
    def session(self) -> AsyncSession:
        """Expose the underlying session for repository construction."""
        return self._session


@asynccontextmanager
async def unit_of_work() -> AsyncGenerator[UnitOfWork, None]:
    """Context manager that provides a UnitOfWork and handles commit/rollback."""
    factory = get_session_factory()
    session = factory()
    uow = UnitOfWork(session)
    try:
        yield uow
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()
