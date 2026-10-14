"""Authorization checks for MAA API endpoints.

Every API endpoint that accesses a resource must verify:
  1. The requester's identity (from MAA headers or API key)
  2. Resource ownership (user_id / project_id / conversation_id)

This module provides reusable authorization helpers.
"""
from __future__ import annotations

import logging

from fastapi import Request

from app.core.exceptions import MAAException

logger = logging.getLogger(__name__)


class AuthorizationError(MAAException):
    def __init__(self, detail: str) -> None:
        super().__init__(
            method="",
            path="",
            status_code=403,
            detail=f"forbidden: {detail}",
        )


class ResourceNotFoundError(MAAException):
    def __init__(self, resource: str, resource_id: str) -> None:
        super().__init__(
            method="",
            path="",
            status_code=404,
            detail=f"{resource} not found: {resource_id}",
        )


def get_maa_context(request: Request) -> dict[str, str]:
    """Extract MAA auth context from request state.

    Set by the request_context_middleware in main.py.
    """
    return {
        "user_id": getattr(request.state, "maa_user_id", "") or "",
        "project_id": getattr(request.state, "maa_project_id", "") or "",
        "conversation_id": getattr(request.state, "maa_conversation_id", "") or "",
        "run_id": getattr(request.state, "maa_run_id", "") or "",
        "trace_id": getattr(request.state, "trace_id", "") or "",
        "request_id": getattr(request.state, "request_id", "") or "",
    }


def verify_conversation_access(
    conversation_user_id: str,
    conversation_project_id: str,
    request: Request,
) -> None:
    """Verify the requester can access the conversation.

    Args:
        conversation_user_id: The conversation's owner user_id.
        conversation_project_id: The conversation's project_id.
        request: The FastAPI request.

    Raises:
        AuthorizationError: If the requester is not authorized.
    """
    ctx = get_maa_context(request)
    req_user = ctx.get("user_id", "")
    req_project = ctx.get("project_id", "")

    # In demo/test mode, allow if headers are empty (fallback behavior)
    if not req_user and not req_project:
        return

    if req_user and conversation_user_id and req_user != conversation_user_id:
        raise AuthorizationError(
            f"user {req_user} cannot access conversation owned by {conversation_user_id}"
        )

    if req_project and conversation_project_id and req_project != conversation_project_id:
        raise AuthorizationError(
            f"project {req_project} cannot access conversation in project {conversation_project_id}"
        )


def verify_run_access(
    run_conversation_id: str,
    request: Request,
    conversation_user_id: str | None = None,
    conversation_project_id: str | None = None,
) -> None:
    """Verify the requester can access the run.

    A run is accessible if the requester can access its parent conversation.
    """
    ctx = get_maa_context(request)
    req_user = ctx.get("user_id", "")
    req_project = ctx.get("project_id", "")

    if not req_user and not req_project:
        return

    # Check user boundary
    if conversation_user_id and req_user and req_user != conversation_user_id:
        raise AuthorizationError(
            f"user {req_user} cannot access run in conversation {run_conversation_id}"
        )

    # Check project boundary
    if conversation_project_id and req_project and req_project != conversation_project_id:
        raise AuthorizationError(
            f"project {req_project} cannot access run in conversation {run_conversation_id}"
        )


def verify_artifact_access(
    artifact_conversation_id: str,
    request: Request,
    conversation_user_id: str | None = None,
    conversation_project_id: str | None = None,
) -> None:
    """Verify the requester can access the artifact.

    An artifact is accessible if the requester can access its parent conversation.
    """
    verify_run_access(
        run_conversation_id=artifact_conversation_id,
        request=request,
        conversation_user_id=conversation_user_id,
        conversation_project_id=conversation_project_id,
    )
