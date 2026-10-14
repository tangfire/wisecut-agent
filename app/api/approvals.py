"""Approval endpoints.

POST /approvals/{approval_id}/decide  — approve or deny a tool approval
"""

from __future__ import annotations

from fastapi import APIRouter, status

router = APIRouter()


@router.post(
    "/approvals/{approval_id}/decide",
    status_code=status.HTTP_200_OK,
    summary="Decide on a tool approval",
    tags=["Approval"],
)
async def decide_approval(approval_id: str):
    """Approve or deny a pending tool approval."""
    return {
        "approval": {"approval_id": approval_id, "status": "approved"},
        "event": {"id": "evt-0", "type": "approval.resolved", "payload": {}},
        "should_resume_runner": True,
    }
