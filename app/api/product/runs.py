"""Run endpoints for Product API."""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.application.sync_services import APIRunService
from app.security.auth import get_current_user_id

logger = logging.getLogger(__name__)

router = APIRouter()


class CreateRunRequest(BaseModel):
    conversation_id: str | None = None
    user_request: str = Field(min_length=1, max_length=10000)
    profile_id: str = Field(default="one-click-quick", pattern="^(one-click-quick|one-click-cocreate)$")
    product_link: str | None = Field(default=None, max_length=2000)
    input_files: list[str] | None = Field(default=None)


class RunResponse(BaseModel):
    id: str
    conversation_id: str
    status: str
    phase: str | None
    started_at: str | None
    finished_at: str | None


class CancelResponse(BaseModel):
    run_id: str
    status: str


def _serialize_run(run: Any) -> RunResponse:
    return RunResponse(
        id=run.id,
        conversation_id=run.conversation_id,
        status=run.status.value if hasattr(run.status, "value") else str(run.status),
        phase=run.phase,
        started_at=run.started_at.isoformat() if run.started_at else None,
        finished_at=run.finished_at.isoformat() if run.finished_at else None,
    )


@router.post("/runs", response_model=RunResponse, status_code=status.HTTP_201_CREATED, tags=["Runs"])
def create_run(request: Request, body: CreateRunRequest):
    """Create a new Agent Film run in the user's default conversation."""
    user_id = get_current_user_id(request)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not authenticated")

    service = APIRunService()
    try:
        run = service.create_run(
            user_id=user_id,
            conversation_id=body.conversation_id,
            user_request=body.user_request,
            profile_id=body.profile_id,
            product_link=body.product_link,
            input_files=body.input_files or [],
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _serialize_run(run)


@router.get("/runs/{run_id}", response_model=RunResponse, tags=["Runs"])
def get_run(request: Request, run_id: str):
    """Get run details."""
    user_id = get_current_user_id(request)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not authenticated")

    service = APIRunService()
    run = service.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run not found")

    if not service.verify_run_access(run_id, user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")

    return _serialize_run(run)


@router.get("/runs/{run_id}/events", tags=["Runs"])
def stream_run_events(request: Request, run_id: str, after_seq: int = 0):
    """Stream run events via SSE with after_seq support."""
    user_id = get_current_user_id(request)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not authenticated")

    service = APIRunService()
    run = service.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run not found")

    if not service.verify_run_access(run_id, user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")

    async def event_generator():
        yield ": connected\n\n"
        for sse_event in service.get_events_for_sse(run_id, after_seq=after_seq):
            yield sse_event

    from sse_starlette import EventSourceResponse
    return EventSourceResponse(event_generator())


@router.post("/runs/{run_id}/cancel", response_model=CancelResponse, tags=["Runs"])
def cancel_run(request: Request, run_id: str):
    """Request cancellation of a run."""
    user_id = get_current_user_id(request)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not authenticated")

    service = APIRunService()
    if not service.verify_run_access(run_id, user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")

    try:
        service.request_cancel(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return CancelResponse(run_id=run_id, status="cancelling")


@router.post("/interactions/{interaction_id}/responses", tags=["Interactions"])
def respond_to_interaction(request: Request, interaction_id: str, body: dict[str, Any]):
    """Submit a response to an interaction."""
    user_id = get_current_user_id(request)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not authenticated")

    service = APIRunService()
    if not service.verify_interaction_access(interaction_id, user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")

    try:
        result = service.respond_to_interaction(interaction_id, body)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return result
