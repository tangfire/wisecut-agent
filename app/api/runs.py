"""Run endpoints with SSE streaming."""

from __future__ import annotations

from fastapi import APIRouter, Request, status
from sse_starlette import EventSourceResponse

from app.application.services import EventService, RunService
from app.persistence.unit_of_work import unit_of_work
from app.protocol.sse import encode_sse_event
from app.security.authz import verify_run_access

router = APIRouter()


def _extract_maa_context(request: Request) -> dict:
    """Extract MAA protocol headers set by the Go Client."""
    return {
        "user_id": request.state.maa_user_id or "",
        "project_id": request.state.maa_project_id or "",
        "conversation_id": request.state.maa_conversation_id,
        "run_id": request.state.maa_run_id,
    }


@router.get("/runs/{run_id}/events", summary="Stream run events (SSE)", tags=["Run"])
async def stream_events(request: Request, run_id: str):
    """Subscribe to run events via SSE with after_seq support.

    Go Client reference: StreamRunEvents / streamRunEventsOnce
      - Query params: after_seq (default 0), live (default true)
      - Accept: text/event-stream
      - SSE format: id / event / data lines, blank line terminates
      - Terminal events: run.completed, run.failed, run.cancelled
      - after_seq < 0 clamped to 0
    """
    after_seq = int(request.query_params.get("after_seq", "0"))
    live = request.query_params.get("live", "true").lower() == "true"
    after_seq = max(0, after_seq)

    _ = _extract_maa_context(request)

    # Verify run exists and check access
    async with unit_of_work() as uow:
        run_repo = uow.runs
        run = await run_repo.get_by_id(run_id)
        if run is None:
            async def error_generator():
                yield encode_sse_event("error", {"error": f"run not found: {run_id}"}, "error-1")
            return EventSourceResponse(error_generator())

        # Permission check: verify requester can access this run's conversation
        conv_repo = uow.conversations
        conv = await conv_repo.get_by_id(run.conversation_id)
        if conv:
            verify_run_access(
                run_conversation_id=run.conversation_id,
                request=request,
                conversation_user_id=conv.user_id,
                conversation_project_id=conv.project_id,
            )

    async def event_generator():
        """Generate SSE events matching Go Client's expectations."""
        # Send initial comment to establish connection (Go Client ignores comments)
        yield ": connected\n\n"

        async with unit_of_work() as uow:
            event_service = EventService(uow)
            async for sse_event in event_service.get_events_for_sse(run_id, after_seq=after_seq):
                yield sse_event

            # If live mode and run is still active, send heartbeat comments
            # Go Client's watchAgentFilmSSEActivity treats any data as activity,
            # so comments keep the connection alive without delivering events.
            if live:
                import asyncio
                for _ in range(3):
                    await asyncio.sleep(1)
                    # Check if run is still non-terminal before next heartbeat
                    current_run = await run_repo.get_by_id(run_id)
                    if current_run and current_run.status in ("completed", "failed", "cancelled"):
                        break
                    yield ": heartbeat\n\n"

    return EventSourceResponse(event_generator())


@router.post("/runs/{run_id}/cancel", status_code=status.HTTP_200_OK, summary="Cancel a run", tags=["Run"])
async def cancel_run(request: Request, run_id: str):
    """Request cancellation of the given run."""
    _ = _extract_maa_context(request)
    async with unit_of_work() as uow:
        run_repo = uow.runs
        run = await run_repo.get_by_id(run_id)
        if run is None:
            from app.core.exceptions import RunNotFound
            raise RunNotFound(run_id)

        # Permission check
        conv_repo = uow.conversations
        conv = await conv_repo.get_by_id(run.conversation_id)
        if conv:
            verify_run_access(
                run_conversation_id=run.conversation_id,
                request=request,
                conversation_user_id=conv.user_id,
                conversation_project_id=conv.project_id,
            )

        service = RunService(uow)
        result = await service.cancel_run(run_id)
        return result
