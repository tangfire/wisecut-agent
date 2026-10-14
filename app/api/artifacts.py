"""Artifact endpoints.

GET /conversations/{conversation_id}/artifacts/{artifact_id}  — get artifact detail
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/conversations/{conversation_id}/artifacts/{artifact_id}", summary="Get artifact detail", tags=["Artifact"])
async def get_artifact(conversation_id: str, artifact_id: str):
    """Return the full artifact data including payload."""
    return {"artifact": {"id": artifact_id, "status": "pending"}}
