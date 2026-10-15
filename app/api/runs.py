"""Run endpoints with SSE streaming (sync DB access)."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Request, status
from sse_starlette import EventSourceResponse

from app.application.sync_services import APIEventService
from app.core.exceptions import RunNotFound
from app.persistence.sync_engine import get_sync_session_factory
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
    """Subscribe to run events via SSE with after_seq support."""
    after_seq = int(request.query_params.get("after_seq", "0"))
    live = request.query_params.get("live", "true").lower() == "true"
    after_seq = max(0, after_seq)

    _ = _extract_maa_context(request)

    # Verify run exists and check access (sync)
    session = get_sync_session_factory()()
    try:
        from app.persistence.models import Conversation, Run
        run = session.get(Run, run_id)
        if run is None:
            async def error_generator():
                yield encode_sse_event("error", {"error": f"run not found: {run_id}"}, "error-1")
            return EventSourceResponse(error_generator())

        conv = session.get(Conversation, run.conversation_id)
        if conv:
            verify_run_access(
                run_conversation_id=run.conversation_id,
                request=request,
                conversation_user_id=conv.user_id,
                conversation_project_id=conv.project_id,
            )
    finally:
        session.close()

    async def event_generator():
        """Generate SSE events matching Go Client's expectations."""
        yield ": connected\n\n"

        event_service = APIEventService()
        for sse_event in event_service.get_events_for_sse(run_id, after_seq=after_seq):
            yield sse_event

        if live:
            import asyncio
            session = get_sync_session_factory()()
            try:
                from app.persistence.models import Run
                for _ in range(3):
                    await asyncio.sleep(1)
                    current_run = session.get(Run, run_id)
                    if current_run and current_run.status in ("completed", "failed", "cancelled"):
                        break
                    yield ": heartbeat\n\n"
            finally:
                session.close()

    return EventSourceResponse(event_generator())


@router.post("/runs/{run_id}/cancel", status_code=status.HTTP_200_OK, summary="Cancel a run", tags=["Run"])
async def cancel_run(request: Request, run_id: str):
    """Request cancellation of the given run."""
    _extract_maa_context(request)
    session = get_sync_session_factory()()
    try:
        from app.persistence.models import Conversation, Run

        run = session.get(Run, run_id)
        if run is None:
            raise RunNotFound(run_id)

        conv = session.get(Conversation, run.conversation_id)
        if conv:
            verify_run_access(
                run_conversation_id=run.conversation_id,
                request=request,
                conversation_user_id=conv.user_id,
                conversation_project_id=conv.project_id,
            )

        if run.status in ("completed", "failed", "cancelled"):
            from app.core.exceptions import RunTerminalError
            raise RunTerminalError(run_id, run.status)

        # Cancel: update status and emit event
        event_service = APIEventService()
        run.status = "cancelled"
        run.finished_at = datetime.now(UTC)
        run.error_message = "cancelled_by_user"
        session.commit()

        event_service.emit_event(
            conversation_id=run.conversation_id,
            run_id=run_id,
            event_type="run.cancelled",
            payload={
                "run_id": run_id,
                "status": "cancelled",
                "finished_at": datetime.now(UTC).isoformat(),
            },
        )

        return {"run_id": run_id, "status": "cancelled"}
    finally:
        session.close()
