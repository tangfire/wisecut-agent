"""Approval endpoints.

POST /approvals/{approval_id}/decide  — approve or deny a tool approval
"""

from __future__ import annotations

from fastapi import APIRouter, Request, status
from pydantic import BaseModel

from app.core.exceptions import ApprovalNotFound
from app.persistence.unit_of_work import unit_of_work
from app.security.authz import verify_conversation_access

router = APIRouter()


class ApprovalDecisionRequest(BaseModel):
    decision: dict


class ApprovalDecisionResponse(BaseModel):
    approval: dict
    event: dict
    should_resume_runner: bool


@router.post(
    "/approvals/{approval_id}/decide",
    response_model=ApprovalDecisionResponse,
    status_code=status.HTTP_200_OK,
    summary="Decide on a tool approval",
    tags=["Approval"],
)
async def decide_approval(request: Request, approval_id: str, body: ApprovalDecisionRequest):
    """Approve or deny a pending tool approval.

    Matches the Go Client's DecideApproval wire format:
      POST /approvals/{approval_id}/decide
      Body: {"decision": {"action": "approve"|"deny", ...}}
      Response: {"approval": {...}, "event": {...}, "should_resume_runner": true}
    """
    # Extract auth context (WP-10 security)
    _ = request.state.maa_user_id or ""
    _ = request.state.maa_project_id or ""

    async with unit_of_work() as uow:
        approval_repo = uow.approvals
        approval = await approval_repo.get_by_id(approval_id)
        if approval is None:
            raise ApprovalNotFound(approval_id)

        # Permission check: verify requester can access the approval's conversation
        conv_repo = uow.conversations
        conv = await conv_repo.get_by_id(approval.conversation_id)
        if conv:
            verify_conversation_access(
                conversation_user_id=conv.user_id,
                conversation_project_id=conv.project_id,
                request=request,
            )

        decision_action = body.decision.get("action", "approve")
        decided = await approval_repo.decide(
            approval_id=approval_id,
            decision=decision_action,
            decision_data=body.decision,
        )

        # Emit approval.resolved event
        event_repo = uow.events
        seq = await event_repo.get_next_seq(approval.conversation_id, approval.run_id)
        await event_repo.create(
            event_id=f"evt-{__import__('uuid').uuid4().hex[:12]}",
            conversation_id=approval.conversation_id,
            run_id=approval.run_id,
            seq=seq,
            event_type="approval.resolved",
            payload={
                "approval_id": approval_id,
                "run_id": approval.run_id,
                "tool_name": approval.tool_name,
                "status": decision_action,
                "decision": body.decision,
                "resolved_at": approval.resolved_at.isoformat() if approval.resolved_at else None,
            },
        )

        return ApprovalDecisionResponse(
            approval={
                "approval_id": approval.id,
                "status": decided.status,
                "decision": decided.decision_json or {},
                "resolved_at": decided.resolved_at.isoformat() if decided.resolved_at else None,
            },
            event={
                "id": f"evt-{seq}",
                "type": "approval.resolved",
                "payload": {"approval_id": approval_id, "status": decision_action},
            },
            should_resume_runner=True,
        )
