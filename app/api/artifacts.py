"""Artifact endpoints.

GET /conversations/{conversation_id}/artifacts/{artifact_id}  — get artifact detail
"""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.core.exceptions import ArtifactNotFound
from app.persistence.unit_of_work import unit_of_work
from app.security.authz import verify_conversation_access

router = APIRouter()


@router.get("/conversations/{conversation_id}/artifacts/{artifact_id}", summary="Get artifact detail", tags=["Artifact"])
async def get_artifact(request: Request, conversation_id: str, artifact_id: str):
    """Return the full artifact data including payload.

    Matches the Go Client's GetArtifact wire format:
      GET /conversations/{conversation_id}/artifacts/{artifact_id}
      Response: {"artifact": {...}}
    """
    async with unit_of_work() as uow:
        artifact_repo = uow.artifacts
        artifact = await artifact_repo.get_by_id(artifact_id)
        if artifact is None:
            raise ArtifactNotFound(conversation_id, artifact_id)

        # Verify artifact belongs to the conversation
        if artifact.conversation_id != conversation_id:
            raise ArtifactNotFound(conversation_id, artifact_id)

        # Permission check: verify via the artifact's conversation
        conv_for_auth = await uow.conversations.get_by_id(artifact.conversation_id)
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
