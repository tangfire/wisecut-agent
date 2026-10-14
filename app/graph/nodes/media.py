"""Media pipeline nodes: materials, digital human, render, validate, publish.

Uses domain logic from app.domain.agent_film for actual implementation.
"""
from __future__ import annotations

from typing import Any

from app.domain.agent_film import (
    match_digital_human,
    publish_artifacts,
    render_video,
    select_materials_for_render,
    validate_video_delivery,
)
from app.graph.state import AgentFilmState


async def collect_materials(state: AgentFilmState) -> dict[str, Any]:
    """Search and select materials for rendering.

    Delegates to select_materials_for_render which:
      - Uses MaterialProvider to search materials
      - Selects top 3 materials for rendering
    """
    return await select_materials_for_render(state)


async def match_digital_human_node(state: AgentFilmState) -> dict[str, Any]:
    """Match digital human to product/script.

    Delegates to match_digital_human which:
      - Quick mode: returns None (skip)
      - Deep mode: uses DigitalHumanProvider to find best match
    """
    return await match_digital_human(state)


async def render_video_node(state: AgentFilmState) -> dict[str, Any]:
    """Trigger video rendering.

    Delegates to render_video which:
      - Uses VideoRenderProvider (demo or real)
      - Updates render_job with video_url, cover_url, format, resolution
      - Handles errors gracefully
    """
    return await render_video(state)


async def validate_delivery_node(state: AgentFilmState) -> dict[str, Any]:
    """Validate rendered video output.

    Checks:
      - video_url is present in render_job
      - video_url passes validate_video_delivery (protocol, SSRF basic check)
    """
    render_job = state.get("render_job", {})
    video_url = render_job.get("video_url")

    if not video_url:
        return {"errors": state.get("errors", []) + [{"node": "validate_delivery", "error": "No video_url in render_job", "fatal": True}]}

    validation = validate_video_delivery(video_url)
    if not validation["valid"]:
        return {"errors": state.get("errors", []) + [{"node": "validate_delivery", "error": validation["error"], "fatal": True}]}

    return {"render_job": {**render_job, "delivery_validated": True}}


async def publish_artifacts_node(state: AgentFilmState) -> dict[str, Any]:
    """Publish final artifacts.

    Delegates to publish_artifacts which:
      - Creates final_video Artifact record
      - Emits artifact.created event
      - Emits business.message event with business_key=final_video
    """
    return await publish_artifacts(state)
