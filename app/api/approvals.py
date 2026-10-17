"""Approval endpoints (sync DB access)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Request, status
from pydantic import BaseModel

from app.application.sync_services import APIEventService
from app.core.exceptions import ApprovalNotFound
from app.persistence.sync_engine import get_sync_session_factory
from app.security.authz import verify_conversation_access

router = APIRouter()


class ApprovalDecisionRequest(BaseModel):
    decision: dict[str, Any]


class ApprovalDecisionResponse(BaseModel):
    approval: dict[str, Any]
    event: dict[str, Any]
    should_resume_runner: bool


@router.post(
    "/approvals/{approval_id}/decide",
    response_model=ApprovalDecisionResponse,
    status_code=status.HTTP_200_OK,
    summary="Decide on a tool approval",
    tags=["Approval"],
)
async def decide_approval(request: Request, approval_id: str, body: ApprovalDecisionRequest) -> ApprovalDecisionResponse:
    """Approve or deny a pending tool approval."""
    _ = request.state.maa_user_id or ""
    _ = request.state.maa_project_id or ""

    session = get_sync_session_factory()()
    try:
        from app.persistence.models import Approval, Conversation

        approval = session.get(Approval, approval_id)
        if approval is None:
            raise ApprovalNotFound(approval_id)

        conv = session.get(Conversation, approval.conversation_id)
        if conv:
            verify_conversation_access(
                conversation_user_id=conv.user_id,
                conversation_project_id=conv.project_id,
                request=request,
            )

        decision_action = body.decision.get("action", "approve")
        approval.status = "approved" if decision_action == "approve" else "denied"
        approval.decision_json = body.decision
        approval.resolved_at = datetime.now(UTC)

        # Emit approval.resolved event
        event_service = APIEventService()
        seq = event_service.emit_event(
            conversation_id=approval.conversation_id,
            run_id=approval.run_id,
            event_type="approval.resolved",
            payload={
                "approval_id": approval_id,
                "run_id": approval.run_id,
                "tool_name": approval.tool_name,
                "status": decision_action,
                "decision": body.decision,
                "resolved_at": approval.resolved_at.isoformat(),
            },
        )
        session.commit()

        return ApprovalDecisionResponse(
            approval={
                "approval_id": approval.id,
                "status": approval.status,
                "decision": approval.decision_json or {},
                "resolved_at": approval.resolved_at.isoformat() if approval.resolved_at else None,
            },
            event={
                "id": f"evt-{seq}",
                "type": "approval.resolved",
                "payload": {"approval_id": approval_id, "status": decision_action},
            },
            should_resume_runner=True,
        )
    finally:
        session.close()
