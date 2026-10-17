"""Artifact endpoints (sync DB access)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from app.core.exceptions import ArtifactNotFound
from app.persistence.sync_engine import get_sync_session_factory
from app.security.authz import verify_conversation_access

router = APIRouter()


@router.get("/conversations/{conversation_id}/artifacts/{artifact_id}", summary="Get artifact detail", tags=["Artifact"])
async def get_artifact(request: Request, conversation_id: str, artifact_id: str) -> dict[str, Any]:
    """Return the full artifact data including payload."""
    session = get_sync_session_factory()()
    try:
        from app.persistence.models import Artifact, Conversation

        artifact = session.get(Artifact, artifact_id)
        if artifact is None:
            raise ArtifactNotFound(conversation_id, artifact_id)

        if artifact.conversation_id != conversation_id:
            raise ArtifactNotFound(conversation_id, artifact_id)

        conv_for_auth = session.get(Conversation, artifact.conversation_id)
        if conv_for_auth:
            verify_conversation_access(
                conversation_user_id=conv_for_auth.user_id,
                conversation_project_id=conv_for_auth.project_id,
                request=request,
            )

        return {
            "artifact": {
                "id": artifact.id,
                "conversation_id": artifact.conversation_id,
                "run_id": artifact.run_id,
                "artifact_type": artifact.artifact_type,
                "uri": artifact.uri,
                "metadata": artifact.metadata_json or {},
                "payload": artifact.payload_json or {},
                "status": artifact.status,
                "created_at": artifact.created_at.isoformat() if artifact.created_at else None,
            }
        }
    finally:
        session.close()
