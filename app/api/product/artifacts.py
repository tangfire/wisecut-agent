"""Artifact endpoints for Product API."""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel

from app.application.sync_services import APIArtifactService
from app.security.auth import get_current_user_id

logger = logging.getLogger(__name__)

router = APIRouter()


class ArtifactResponse(BaseModel):
    id: str
    run_id: str
    artifact_type: str
    uri: str | None
    status: str
    created_at: str


class ArtifactListResponse(BaseModel):
    items: list[ArtifactResponse]
    total: int


def _serialize_artifact(a: Any) -> ArtifactResponse:
    return ArtifactResponse(
        id=a.id,
        run_id=a.run_id,
        artifact_type=a.artifact_type,
        uri=a.uri,
        status=a.status.value if hasattr(a.status, "value") else str(a.status),
        created_at=a.created_at.isoformat() if a.created_at else None,
    )


@router.get("/projects/{project_id}/artifacts", response_model=ArtifactListResponse, tags=["Artifacts"])
def list_project_artifacts(request: Request, project_id: str):
    """List all artifacts for a project."""
    user_id = get_current_user_id(request)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not authenticated")

    service = APIArtifactService()
    if not service.verify_project_access(project_id, user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")

    artifacts = service.list_by_project(project_id)
    return ArtifactListResponse(items=[_serialize_artifact(a) for a in artifacts], total=len(artifacts))


@router.get("/artifacts/{artifact_id}", response_model=ArtifactResponse, tags=["Artifacts"])
def get_artifact(request: Request, artifact_id: str):
    """Get artifact details."""
    user_id = get_current_user_id(request)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not authenticated")

    service = APIArtifactService()
    artifact = service.get_artifact(artifact_id)
    if artifact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="artifact not found")

    if not service.verify_artifact_access(artifact_id, user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")

    return _serialize_artifact(artifact)


@router.get("/artifacts/{artifact_id}/download", tags=["Artifacts"])
def download_artifact(request: Request, artifact_id: str):
    """Get a presigned download URL for the artifact."""
    user_id = get_current_user_id(request)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not authenticated")

    service = APIArtifactService()
    artifact = service.get_artifact(artifact_id)
    if artifact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="artifact not found")

    if not service.verify_artifact_access(artifact_id, user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")

    url = service.get_download_url(artifact_id)
    return {"download_url": url}
