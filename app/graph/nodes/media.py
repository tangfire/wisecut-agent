"""Media nodes: materials, digital human, rendering, validation, publishing.

WP-09 will implement the actual provider calls.  WP-06 provides stubs.
"""

from __future__ import annotations

from app.graph.state import AgentFilmState


async def collect_materials(state: AgentFilmState) -> dict[str, Any]:
    """Search and select materials.

    WP-09: replace with actual material provider call.
    """
    return {"materials": state.get("materials", [])}


async def match_digital_human(state: AgentFilmState) -> dict[str, Any]:
    """Match digital human to product/script.

    WP-09: replace with actual digital human provider call.
    """
    return {"digital_human": state.get("digital_human")}


async def render_video(state: AgentFilmState) -> dict[str, Any]:
    """Trigger video rendering.

    WP-09: replace with actual video render provider call.
    """
    return {"render_job": {}}


async def validate_delivery(state: AgentFilmState) -> dict[str, Any]:
    """Validate rendered video.

    WP-09: replace with actual validation logic.
    """
    return {}


async def publish_artifacts(state: AgentFilmState) -> dict[str, Any]:
    """Publish final artifacts.

    WP-09: replace with actual artifact publishing.
    """
    return {"artifacts": state.get("artifacts", [])}
