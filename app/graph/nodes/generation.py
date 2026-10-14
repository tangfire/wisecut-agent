"""Generation nodes: prepare generation and request approval.

Uses domain logic from app.domain.agent_film for actual preparation.
"""
from __future__ import annotations

from typing import Any

from app.domain.agent_film import build_generation_approval, prepare_generation
from app.graph.state import AgentFilmState


async def prepare_generation_node(state: AgentFilmState) -> dict[str, Any]:
    """Prepare materials and settings for generation.

    - Searches materials via MaterialProvider
    - Calculates estimated cost (billing, points)
    - Sets up render_job configuration

    Returns state update with materials and render_job.
    """
    return await prepare_generation(state)


async def request_generation_approval_node(state: AgentFilmState) -> dict[str, Any]:
    """Emit approval.required for generation start.

    Returns an approval payload that the Worker will convert to an
    `approval.required` event with the confirm_generation_start card.

    The payload includes:
      - cost breakdown (duration, points, digital human)
      - auto_approve_countdown_seconds (10s)
      - product_name, shot_count
    """
    approval = build_generation_approval(state)
    return {
        "pending_approval": approval,
    }
