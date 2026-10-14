"""Script generation nodes: creative strategy, script, and storyboard review.

Uses domain logic from app.domain.agent_film for actual generation.
"""
from __future__ import annotations

from typing import Any

from app.domain.agent_film import (
    build_storyboard_interaction,
    generate_creative_strategy,
    generate_script,
)
from app.graph.state import AgentFilmState


async def generate_creative_strategy_node(state: AgentFilmState) -> dict[str, Any]:
    """Generate marketing creative strategy.

    Produces:
      - marketing_angle (promotional/new_launch/brand_story/feature_focused/general)
      - tone (concise/detailed)
      - key_messages (top 3 selling points)
      - target_emotion (fun/warm/premium/urgency/neutral)
    """
    return await generate_creative_strategy(state)


async def generate_script_node(state: AgentFilmState) -> dict[str, Any]:
    """Generate video script.

    Produces structured script with:
      - title, total_duration, style, language
      - segments (each with time, camera_desc, script_content, screen_text, core_purpose)
    """
    return await generate_script(state)


async def request_storyboard_review_node(state: AgentFilmState) -> dict[str, Any]:
    """Emit storyboard review interaction and pause.

    Returns a table_review interaction payload with:
      - 3-column table: shot/time, camera_desc, core_purpose
      - Actions: approve, modify, deny, regenerate
    """
    interaction = build_storyboard_interaction(state)
    return {
        "pending_interaction": interaction,
    }
