"""Conversation endpoints with real persistence."""

from __future__ import annotations

from fastapi import APIRouter, Request, status
from pydantic import BaseModel, Field

from app.application.services import ConversationService
from app.core.exceptions import ConversationNotFound
from app.persistence.unit_of_work import unit_of_work
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
    conversation: dict
    active_run: dict | None
    messages: list[dict]
    interactions: list[dict]
    recent_events: list[dict]


def _extract_maa_context(request: Request) -> dict:
    """Extract MAA protocol headers set by the Go Client."""
    user_id = getattr(request.state, "maa_user_id", "") or ""
    project_id = getattr(request.state, "maa_project_id", "") or ""
    # WP-11: no fixed fallback; generate UUID-based IDs for local dev
    if not user_id:
        user_id = f"dev-{__import__('uuid').uuid4().hex[:8]}"
    if not project_id:
        project_id = f"dev-{__import__('uuid').uuid4().hex[:8]}"
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
async def create_conversation(request: Request, body: CreateConversationRequest):
    """Create a new MAA conversation.

    Matches the Go Client's createConversation wire format:
      - title: first 24 chars of user content or explicit title
      - agent_profile_id: top-level field (also echoed in metadata)
      - metadata: source, local_run_id, user_id, project_id, mode, agent_profile_id, response_language
    """
    maa_context = _extract_maa_context(request)
    profile_id = body.agent_profile_id or "one-click-quick"
    mode = "deep" if "cocreate" in profile_id else "quick"

    # Build metadata matching Go Client's createConversation
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

    async with unit_of_work() as uow:
        service = ConversationService(uow)
        result = await service.create(
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
async def get_conversation(request: Request, conversation_id: str):
    """Get conversation snapshot with active run, messages, interactions, and events."""
    _extract_maa_context(request)
    async with unit_of_work() as uow:
        conv_repo = uow.conversations
        conv = await conv_repo.get_by_id(conversation_id)
        if conv is None:
            raise ConversationNotFound(conversation_id)
        verify_conversation_access(
            conversation_user_id=conv.user_id,
            conversation_project_id=conv.project_id,
            request=request,
        )
        service = ConversationService(uow)
        detail = await service.get_detail(conversation_id)
        if detail is None:
            raise ConversationNotFound(conversation_id)
        return ConversationDetailResponse(**detail)
