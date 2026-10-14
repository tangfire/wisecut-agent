"""Script generation nodes: creative strategy, script, and storyboard review."""

from __future__ import annotations

from app.graph.state import AgentFilmState


async def generate_creative_strategy(state: AgentFilmState) -> dict[str, Any]:
    """Generate marketing creative strategy via LLM.

    WP-08: replace stub with actual LLM call.
    """
    return {"creative_strategy": state.get("creative_strategy", {})}


async def generate_script(state: AgentFilmState) -> dict[str, Any]:
    """Generate video script via LLM.

    WP-08: replace stub with actual LLM call.
    """
    return {"script": state.get("script", {})}


async def request_storyboard_review(state: AgentFilmState) -> dict[str, Any]:
    """Emit storyboard review interaction and pause."""
    interaction = {
        "intent": "review_storyboard_script",
        "cards": [],
        "actions": ["approve", "modify", "deny", "regenerate"],
        "status": "pending",
    }
    return {
        "pending_interaction": interaction,
    }
