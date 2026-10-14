"""Conversation endpoints.

POST /conversations        — create conversation
GET  /conversations/{id}   — get conversation detail
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

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


class ConversationResponse(BaseModel):
    id: str
    status: str
    metadata: dict[str, str]


@router.post(
    "",
    response_model=CreateConversationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new conversation",
    tags=["Conversation"],
)
async def create_conversation(request: CreateConversationRequest):
    """Create a new MAA conversation."""
    conversation_id = f"conv-{__import__('uuid').uuid4().hex[:12]}"
    return CreateConversationResponse(
        conversation_id=conversation_id,
        langgraph_thread_id=conversation_id,
        status="created",
    )


@router.get(
    "/{conversation_id}",
    response_model=ConversationDetailResponse,
    summary="Get conversation detail",
    tags=["Conversation"],
)
async def get_conversation(conversation_id: str):
    """Get conversation snapshot with active run, messages, interactions, and events."""
    from app.core.exceptions import ConversationNotFound
    raise ConversationNotFound(conversation_id)
