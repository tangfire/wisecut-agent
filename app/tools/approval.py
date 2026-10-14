"""Approval Service: create, query, and decide approvals.

Aligns with Go Client's `DecideApproval` contract:
  POST /approvals/{approval_id}/decide
  body: {"decision": {"type": "approve"|"reject"|"edit", ...}}
  returns: {approval, event, should_resume_runner}
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.persistence.models import Approval, ApprovalStatus
from app.persistence.repositories import (
    ApprovalRepository,
    EventRepository,
    OutboxRepository,
)
from app.persistence.unit_of_work import unit_of_work
from app.protocol.language import generate_id

logger = logging.getLogger(__name__)


class ApprovalService:
    """Manage approval lifecycle.

    Usage:
        service = ApprovalService()

        # Create approval
        approval = await service.create(
            conversation_id="conv-1",
            run_id="run-1",
            tool_name="render_video",
            arguments={"duration_seconds": 30},
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        )

        # Decide
        result = await service.decide(
            approval_id=approval.id,
            decision_type="approve",
            decision_data={"note": "Approved by user"},
        )
    """

    async def create(
        self,
        conversation_id: str,
        run_id: str,
        tool_name: str,
        arguments: dict[str, Any],
        expires_at: datetime | None = None,
        tool_execution_id: str | None = None,
    ) -> dict[str, Any]:
        """Create a new approval request.

        Emits an ``approval.required`` event.
        """
        approval_id = generate_id("approval")
        event_id = generate_id("event")
        now = datetime.now(timezone.utc)

        async with unit_of_work() as uow:
            approval_repo = ApprovalRepository(uow.session)
            event_repo = EventRepository(uow.session)
            outbox_repo = OutboxRepository(uow.session)

            await approval_repo.create(
                approval_id=approval_id,
                conversation_id=conversation_id,
                run_id=run_id,
                tool_name=tool_name,
                arguments=arguments,
                expires_at=expires_at,
            )

            # Link approval to tool_execution if provided
            if tool_execution_id:
                from sqlalchemy import update
                await uow.session.execute(
                    update(ToolExecutionRepository._model)
                    .where(ToolExecutionRepository._model.id == tool_execution_id)
                    .values(metadata_json={"approval_id": approval_id})
                )

            # Emit approval.required event
            seq = await event_repo.get_next_seq(conversation_id, run_id)
            await event_repo.create(
                event_id=event_id,
                conversation_id=conversation_id,
                run_id=run_id,
                seq=seq,
                event_type="approval.required",
                payload={
                    "approval_id": approval_id,
                    "tool_name": tool_name,
                    "tool_args": arguments,
                    "allowed_decisions": ["approve", "reject", "edit"],
                    "description": f"Approval required for tool: {tool_name}",
                    "expires_at": expires_at.isoformat() if expires_at else None,
                },
            )

            # Add to outbox for SSE delivery
            await outbox_repo.enqueue(
                aggregate_type="approval",
                aggregate_id=approval_id,
                event_type="approval.required",
                payload={
                    "approval_id": approval_id,
                    "tool_name": tool_name,
                    "allowed_decisions": ["approve", "reject", "edit"],
                },
            )

        logger.info(
            "Approval created: %s tool=%s run=%s",
            approval_id, tool_name, run_id,
        )

        return {
            "id": approval_id,
            "conversation_id": conversation_id,
            "run_id": run_id,
            "tool_name": tool_name,
            "status": ApprovalStatus.PENDING.value,
            "arguments": arguments,
            "created_at": now.isoformat(),
        }

    async def get(self, approval_id: str) -> dict[str, Any] | None:
        """Get an approval by ID."""
        async with unit_of_work() as uow:
            repo = ApprovalRepository(uow.session)
            approval = await repo.get_by_id(approval_id)
            if approval is None:
                return None
            return {
                "id": approval.id,
                "conversation_id": approval.conversation_id,
                "run_id": approval.run_id,
                "tool_name": approval.tool_name,
                "arguments": approval.arguments_json,
                "status": approval.status.value,
                "decision": approval.decision_json,
                "expires_at": approval.expires_at.isoformat() if approval.expires_at else None,
                "created_at": approval.created_at.isoformat(),
                "resolved_at": approval.resolved_at.isoformat() if approval.resolved_at else None,
            }

    async def decide(
        self,
        approval_id: str,
        decision_type: str,
        decision_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Decide an approval.

        Args:
            approval_id: The approval ID.
            decision_type: One of "approve", "reject", "edit".
            decision_data: Optional additional decision data.

        Returns:
            Dict with approval, event, and should_resume_runner flag.

        Raises:
            ValueError: If approval not found or already decided.
        """
        event_id = generate_id("event")
        decision_data = decision_data or {}
        decision_data["type"] = decision_type

        async with unit_of_work() as uow:
            approval_repo = ApprovalRepository(uow.session)
            event_repo = EventRepository(uow.session)
            outbox_repo = OutboxRepository(uow.session)

            approval = await approval_repo.get_by_id(approval_id)
            if approval is None:
                raise ValueError(f"Approval {approval_id!r} not found")

            if approval.status != ApprovalStatus.PENDING:
                raise ValueError(
                    f"Approval {approval_id!r} already decided: {approval.status.value}"
                )

            # Map decision type to ApprovalStatus
            status_map = {
                "approve": ApprovalStatus.APPROVED,
                "reject": ApprovalStatus.DENIED,
                "edit": ApprovalStatus.APPROVED,
            }
            new_status = status_map.get(decision_type, ApprovalStatus.DENIED)

            await approval_repo.decide(
                approval_id=approval_id,
                decision=decision_type,
                decision_data=decision_data,
            )

            # Emit approval.resolved event
            seq = await event_repo.get_next_seq(approval.conversation_id, approval.run_id)
            await event_repo.create(
                event_id=event_id,
                conversation_id=approval.conversation_id,
                run_id=approval.run_id,
                seq=seq,
                event_type="approval.resolved",
                payload={
                    "approval_id": approval_id,
                    "tool_name": approval.tool_name,
                    "decision": decision_type,
                    "should_resume_runner": True,
                },
            )

            # Outbox for SSE
            await outbox_repo.enqueue(
                aggregate_type="approval",
                aggregate_id=approval_id,
                event_type="approval.resolved",
                payload={
                    "approval_id": approval_id,
                    "decision": decision_type,
                    "should_resume_runner": True,
                },
            )

        logger.info(
            "Approval decided: %s type=%s run=%s",
            approval_id, decision_type, approval.run_id,
        )

        return {
            "approval": {
                "id": approval_id,
                "status": new_status.value,
                "decision": decision_data,
            },
            "event": {
                "type": "approval.resolved",
                "approval_id": approval_id,
            },
            "should_resume_runner": True,
        }

    async def get_pending(self, run_id: str) -> list[dict[str, Any]]:
        """Get all pending approvals for a run."""
        from sqlalchemy import select

        async with unit_of_work() as uow:
            stmt = (
                select(Approval)
                .where(Approval.run_id == run_id)
                .where(Approval.status == ApprovalStatus.PENDING)
                .order_by(Approval.created_at)
            )
            result = await uow.session.execute(stmt)
            approvals = result.scalars().all()

        return [
            {
                "id": a.id,
                "tool_name": a.tool_name,
                "arguments": a.arguments_json,
                "status": a.status.value,
                "created_at": a.created_at.isoformat(),
                "expires_at": a.expires_at.isoformat() if a.expires_at else None,
            }
            for a in approvals
        ]
