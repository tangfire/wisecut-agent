"""Generation nodes: prepare generation and request approval."""

from __future__ import annotations

from app.graph.state import AgentFilmState


async def prepare_generation(state: AgentFilmState) -> dict[str, Any]:
    """Prepare materials and settings for generation.

    WP-08/WP-09: replace stub with actual preparation logic.
    """
    return {}


async def request_generation_approval(state: AgentFilmState) -> dict[str, Any]:
    """Emit approval.required and pause for user approval.

    Returns an approval payload that the Worker will convert to an
    `approval.required` event.
    """
    from app.graph.profiles import get_profile
    profile = get_profile(state.get("profile_id", "one-click-quick"))

    approval = {
        "tool_name": "render_video",
        "arguments": {
            "aspect_ratio": profile.default_aspect_ratio,
            "duration": profile.default_duration,
            "language": state.get("language", "zh-CN"),
        },
        "status": "pending",
    }
    return {
        "pending_approval": approval,
    }
