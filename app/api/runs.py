"""Run endpoints.

GET /runs/{run_id}/events    — SSE event stream
POST /runs/{run_id}/cancel   — request run cancellation
"""

from __future__ import annotations

from fastapi import APIRouter, Request, status

router = APIRouter()


@router.get("/runs/{run_id}/events", summary="Stream run events (SSE)", tags=["Run"])
async def stream_events(run_id: str, request: Request):
    """Subscribe to run events via SSE."""
    from fastapi.responses import Response

    return Response(
        content=b"",
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/runs/{run_id}/cancel", status_code=status.HTTP_200_OK, summary="Cancel a run", tags=["Run"])
async def cancel_run(run_id: str):
    """Request cancellation of the given run."""
    return {}
