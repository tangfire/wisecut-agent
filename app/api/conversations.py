"""Conversation endpoints using synchronous database access."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request, status
from pydantic import BaseModel, Field

from app.application.sync_services import APIConversationService
from app.core.exceptions import ConversationNotFound
from app.security.authz import verify_conversation_access

router = APIRouter()


class CreateConversationRequest(BaseModel):
    title: str = Field(max_length=200)
    agent_profile_id: str | None = None
    metadata: dict[str, str] | None = None


class CreateConversationResponse(BaseModel):
    conversation_id: str
    langgraph_thread_id: str
    status: str


class ConversationDetailResponse(BaseModel):
    conversation: dict[str, Any]
    active_run: dict[str, Any] | None
    messages: list[dict[str, Any]]
    interactions: list[dict[str, Any]]
    recent_events: list[dict[str, Any]]


def _extract_maa_context(request: Request) -> dict[str, str]:
    """Extract MAA protocol headers set by the Go Client.

    WP-10: no random-identity fallback.  In demo mode the headers
    may be empty (contract fixtures).  In staging/production the
    service auth middleware already validated the request.
    """
    user_id = getattr(request.state, "maa_user_id", "") or ""
    project_id = getattr(request.state, "maa_project_id", "") or ""
    return {
        "user_id": user_id,
        "project_id": project_id,
        "conversation_id": getattr(request.state, "maa_conversation_id", "") or "",
        "run_id": getattr(request.state, "maa_run_id", "") or "",
    }


@router.post(
    "",
    response_model=CreateConversationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new conversation",
    tags=["Conversation"],
)
async def create_conversation(request: Request, body: CreateConversationRequest) -> CreateConversationResponse:
    """Create a new MAA conversation."""
    maa_context = _extract_maa_context(request)
    profile_id = body.agent_profile_id or "one-click-quick"
    mode = "deep" if "cocreate" in profile_id else "quick"

    meta = dict(body.metadata or {})
    meta.update({
        "source": "wisecut-agent-film",
        "local_run_id": maa_context["run_id"],
        "user_id": maa_context["user_id"],
        "project_id": maa_context["project_id"],
        "mode": mode,
        "agent_profile_id": profile_id,
        "response_language": "zh-CN",
    })

    service = APIConversationService()
    result = service.create(
        title=body.title,
        user_id=maa_context["user_id"],
        project_id=maa_context["project_id"],
        profile_id=profile_id,
        mode=mode,
        metadata=meta,
    )
    return CreateConversationResponse(**result)


@router.get(
    "/{conversation_id}",
    response_model=ConversationDetailResponse,
    summary="Get conversation detail",
    tags=["Conversation"],
)
async def get_conversation(request: Request, conversation_id: str) -> ConversationDetailResponse:
    """Get conversation snapshot."""
    _extract_maa_context(request)
    service = APIConversationService()
    conv = service.get_by_id(conversation_id)
    if conv is None:
        raise ConversationNotFound(conversation_id)
    verify_conversation_access(
        conversation_user_id=conv.user_id,
        conversation_project_id=conv.project_id,
        request=request,
    )
    detail = service.get_detail(conversation_id)
    if detail is None:
        raise ConversationNotFound(conversation_id)
    return ConversationDetailResponse(**detail)
