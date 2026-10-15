"""Message endpoints using synchronous database access."""

from __future__ import annotations

from fastapi import APIRouter, Request, status

from app.application.sync_services import APIMessageService
from app.core.exceptions import ConversationNotFound
from app.persistence.sync_engine import get_sync_session_factory
from app.security.authz import verify_conversation_access

router = APIRouter()


def _extract_maa_context(request: Request) -> dict:
    """Extract MAA protocol headers set by the Go Client."""
    user_id = getattr(request.state, "maa_user_id", "") or ""
    project_id = getattr(request.state, "maa_project_id", "") or ""
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


def _get_sync_session():
    """Get a sync DB session for read operations."""
    return get_sync_session_factory()()


@router.get("/conversations/{conversation_id}/messages", summary="List messages", tags=["Message"])
async def list_messages(request: Request, conversation_id: str):
    """Return all messages for the conversation."""
    from app.persistence.models import Conversation, Message

    _extract_maa_context(request)
    session = _get_sync_session()
    try:
        conv = session.get(Conversation, conversation_id)
        if conv is None:
            raise ConversationNotFound(conversation_id)
        verify_conversation_access(
            conversation_user_id=conv.user_id,
            conversation_project_id=conv.project_id,
            request=request,
        )
        messages = session.query(Message).filter(
            Message.conversation_id == conversation_id
        ).order_by(Message.created_at.desc()).limit(100).all()
        return [
            {
                "id": m.id,
                "conversation_id": m.conversation_id,
                "run_id": m.run_id,
                "role": m.role,
                "type": m.type,
                "content": m.content,
                "metadata": m.metadata_json or {},
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in messages
        ]
    finally:
        session.close()


@router.post("/conversations/{conversation_id}/messages", status_code=status.HTTP_200_OK, summary="Post a message", tags=["Message"])
async def post_message(request: Request, conversation_id: str, body: dict):
    """Accept message, guidance, or interaction_response.

    Publishes a Run command to RabbitMQ. The Worker handles DB writes.
    """
    maa_context = _extract_maa_context(request)
    message_type = body.get("type", "message")
    content = body.get("content", "")
    metadata = body.get("metadata", {})

    # Verify conversation exists (sync read)
    session = _get_sync_session()
    try:
        from app.persistence.models import Conversation
        conv = session.get(Conversation, conversation_id)
        if conv is None:
            raise ConversationNotFound(conversation_id)
        verify_conversation_access(
            conversation_user_id=conv.user_id,
            conversation_project_id=conv.project_id,
            request=request,
        )
    finally:
        session.close()

    # Handle interaction_response
    if message_type == "interaction_response":
        interaction_id = body.get("interaction_id", "")
        action = body.get("action", "")
        client_action_id = body.get("client_action_id", "")
        if not interaction_id or not action:
            from app.core.exceptions import ValidationError
            raise ValidationError(
                path=f"/conversations/{conversation_id}/messages",
                detail="interaction_response requires interaction_id and action",
            )
        service = APIMessageService()
        return service.post_interaction_response(
            conversation_id=conversation_id,
            run_id=maa_context["run_id"] or f"run-{__import__('uuid').uuid4().hex[:12]}",
            interaction_id=interaction_id,
            action=action,
            content=body.get("content", ""),
            client_action_id=client_action_id,
            metadata=metadata,
        )

    # Regular message: publish to RabbitMQ
    service = APIMessageService()
    return service.post_message(
        conversation_id=conversation_id,
        message_type=message_type,
        content=content,
        role="user",
        metadata=metadata,
        request_id=metadata.get("request_id") if isinstance(metadata, dict) else None,
    )
