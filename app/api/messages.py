"""Message endpoints with idempotency."""

from __future__ import annotations

from fastapi import APIRouter, Request, status

from app.application.services import MessageService
from app.persistence.unit_of_work import unit_of_work
from app.security.authz import verify_conversation_access

router = APIRouter()


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


@router.get("/conversations/{conversation_id}/messages", summary="List conversation messages", tags=["Message"])
async def list_messages(request: Request, conversation_id: str):
    """Return all messages for the conversation."""
    _ = _extract_maa_context(request)
    async with unit_of_work() as uow:
        conv_repo = uow.conversations
        conv = await conv_repo.get_by_id(conversation_id)
        if conv is None:
            from app.core.exceptions import ConversationNotFound
            raise ConversationNotFound(conversation_id)
        verify_conversation_access(
            conversation_user_id=conv.user_id,
            conversation_project_id=conv.project_id,
            request=request,
        )
        repo = uow.messages
        messages = await repo.get_by_conversation(conversation_id)
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


@router.post("/conversations/{conversation_id}/messages", status_code=status.HTTP_200_OK, summary="Post a message", tags=["Message"])
async def post_message(request: Request, conversation_id: str, body: dict):
    """Accept message, guidance, or interaction_response.

    Message types:
      - message: regular user message or start-run content
      - guidance: user guidance during active run
      - interaction_response: answer to an interaction card
    """
    maa_context = _extract_maa_context(request)
    message_type = body.get("type", "message")
    content = body.get("content", "")
    metadata = body.get("metadata", {})

    # Extract request_id for idempotency (from metadata or generate)
    request_id = metadata.get("request_id") if metadata else None

    # Determine run_id: prefer header, then metadata, then active run, then generate
    run_id = maa_context["run_id"] or (metadata.get("run_id", "") if metadata else "")
    if not run_id:
        async with unit_of_work() as uow:
            run = await uow.runs.get_active_run(conversation_id)
            if run:
                run_id = run.id

    if not run_id:
        run_id = f"run-{__import__('uuid').uuid4().hex[:12]}"

    # Handle interaction_response specially
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
        async with unit_of_work() as uow:
            conv_repo = uow.conversations
            conv = await conv_repo.get_by_id(conversation_id)
            if conv is None:
                from app.core.exceptions import ConversationNotFound
                raise ConversationNotFound(conversation_id)
            verify_conversation_access(
                conversation_user_id=conv.user_id,
                conversation_project_id=conv.project_id,
                request=request,
            )
            service = MessageService(uow)
            result = await service.post_interaction_response(
                conversation_id=conversation_id,
                run_id=run_id,
                interaction_id=interaction_id,
                action=action,
                content=body.get("content", ""),
                client_action_id=client_action_id,
                metadata=metadata,
            )
            return result

    async with unit_of_work() as uow:
        conv_repo = uow.conversations
        conv = await conv_repo.get_by_id(conversation_id)
        if conv is None:
            from app.core.exceptions import ConversationNotFound
            raise ConversationNotFound(conversation_id)
        verify_conversation_access(
            conversation_user_id=conv.user_id,
            conversation_project_id=conv.project_id,
            request=request,
        )
        service = MessageService(uow)
        result = await service.post_message(
            conversation_id=conversation_id,
            run_id=run_id,
            message_type=message_type,
            content=content,
            role="user",
            metadata=metadata,
            request_id=request_id,
        )
        return result
