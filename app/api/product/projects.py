"""Project endpoints for Product API."""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.application.sync_services import APIProjectService
from app.security.auth import get_current_user_id

logger = logging.getLogger(__name__)

router = APIRouter()


class CreateProjectRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)


class UpdateProjectRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    status: str | None = Field(default=None, pattern="^(active|archived)$")


class ProjectResponse(BaseModel):
    id: str
    workspace_id: str
    name: str
    description: str | None
    status: str
    created_by: str
    created_at: str
    updated_at: str


class ProjectListResponse(BaseModel):
    items: list[ProjectResponse]
    total: int
    offset: int
    limit: int


def _serialize_project(p: Any) -> ProjectResponse:
    return ProjectResponse(
        id=p.id,
        workspace_id=p.workspace_id,
        name=p.name,
        description=p.description,
        status=p.status.value if hasattr(p.status, "value") else str(p.status),
        created_by=p.created_by,
        created_at=p.created_at.isoformat() if p.created_at else None,
        updated_at=p.updated_at.isoformat() if p.updated_at else None,
    )


@router.get("/projects", response_model=ProjectListResponse, tags=["Projects"])
def list_projects(request: Request, offset: int = 0, limit: int = 20):
    """List projects in the user's default workspace."""
    user_id = get_current_user_id(request)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not authenticated")

    service = APIProjectService()
    workspace_id = service.get_default_workspace(user_id)
    projects, total = service.list_projects(workspace_id, offset=offset, limit=limit)
    return ProjectListResponse(
        items=[_serialize_project(p) for p in projects],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.post("/projects", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED, tags=["Projects"])
def create_project(request: Request, body: CreateProjectRequest):
    """Create a new project in the user's default workspace."""
    user_id = get_current_user_id(request)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not authenticated")

    service = APIProjectService()
    workspace_id = service.get_default_workspace(user_id)
    project = service.create_project(
        workspace_id=workspace_id,
        name=body.name,
        description=body.description,
        created_by=user_id,
    )
    return _serialize_project(project)


@router.get("/projects/{project_id}", response_model=ProjectResponse, tags=["Projects"])
def get_project(request: Request, project_id: str):
    """Get project details."""
    user_id = get_current_user_id(request)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not authenticated")

    service = APIProjectService()
    project = service.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="project not found")

    # Verify workspace ownership
    workspace = service.get_workspace(project.workspace_id)
    if workspace is None or workspace.owner_user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")

    return _serialize_project(project)


@router.patch("/projects/{project_id}", response_model=ProjectResponse, tags=["Projects"])
def update_project(request: Request, project_id: str, body: UpdateProjectRequest):
    """Update project name/description/status."""
    user_id = get_current_user_id(request)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not authenticated")

    service = APIProjectService()
    project = service.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="project not found")

    workspace = service.get_workspace(project.workspace_id)
    if workspace is None or workspace.owner_user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")

    updated = service.update_project(
        project_id=project_id,
        name=body.name,
        description=body.description,
        status=body.status,
    )
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="project not found")
    return _serialize_project(updated)


@router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Projects"])
def delete_project(request: Request, project_id: str):
    """Soft-delete a project."""
    user_id = get_current_user_id(request)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not authenticated")

    service = APIProjectService()
    project = service.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="project not found")

    workspace = service.get_workspace(project.workspace_id)
    if workspace is None or workspace.owner_user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")

    service.delete_project(project_id)
    return None
