"""Product context node: extracts product information from link and files."""

from __future__ import annotations

from app.graph.state import AgentFilmState


async def collect_product_context(state: AgentFilmState) -> dict[str, Any]:
    """Extract product context from product_link and input_files.

    WP-08: replace stub with actual LLM/tool-based extraction.
    """
    # Stub: pass through existing product_context or return empty
    return {"product_context": state.get("product_context", {})}


async def request_product_context_review(state: AgentFilmState) -> dict[str, Any]:
    """Emit interaction.requested and pause for user input.

    Returns an interaction payload that the Worker will convert to an
    `interaction.requested` event.
    """
    from app.graph.profiles import get_profile
    profile = get_profile(state.get("profile_id", "one-click-quick"))

    interaction = {
        "intent": "confirm_extracted_product_context",
        "cards": [],
        "actions": ["approve", "modify", "deny"],
        "status": "pending",
    }

    return {
        "pending_interaction": interaction,
    }
