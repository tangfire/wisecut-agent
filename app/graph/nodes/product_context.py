"""Product context node: extracts product information from link and files.

Uses domain logic from app.domain.agent_film for actual extraction.
"""
from __future__ import annotations

from typing import Any

from app.domain.agent_film import build_product_context_interaction, extract_product_context
from app.graph.state import AgentFilmState


async def collect_product_context(state: AgentFilmState) -> dict[str, Any]:
    """Extract product context from product_link and input_files.

    Uses ProductResearchProvider to extract:
      - product_name, product_description, target_audience
      - selling_points, images

    For quick mode, fills defaults if extraction fails.
    """
    return await extract_product_context(state)


async def request_product_context_review(state: AgentFilmState) -> dict[str, Any]:
    """Emit interaction.requested for product context confirmation.

    Returns an interaction payload that the Worker will convert to an
    `interaction.requested` event with the confirm_extracted_product_context card.
    """
    interaction = build_product_context_interaction(state)
    return {
        "pending_interaction": interaction,
    }
