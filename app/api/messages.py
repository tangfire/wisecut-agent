"""Message endpoints.

GET  /conversations/{conversation_id}/messages  — list messages
POST /conversations/{conversation_id}/messages  — post message / guidance / interaction_response
"""

from __future__ import annotations

from fastapi import APIRouter, status

router = APIRouter()


@router.get("/conversations/{conversation_id}/messages", summary="List conversation messages", tags=["Message"])
async def list_messages(conversation_id: str):
    """Return all messages for the conversation."""
    return []


@router.post("/conversations/{conversation_id}/messages", status_code=status.HTTP_200_OK, summary="Post a message", tags=["Message"])
async def post_message(conversation_id: str):
    """Accept message, guidance, or interaction_response."""
    return {
        "conversation_id": conversation_id,
        "run_id": "stub-run-id",
        "accepted_as_inbox": True,
        "events_url": f"/runs/stub-run-id/events",
    }
