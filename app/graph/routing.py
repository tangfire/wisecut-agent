"""Graph routing functions: conditional edges that determine the flow.

Each router returns a string matching a node name in the StateGraph.

Routers:
  - needs_product_confirmation: does the product context need user review?
  - review_script_or_storyboard: does the script/storyboard need user review?
  - is_terminal: is the run in a terminal state?
  - should_retry: can we retry after an error?
"""

from __future__ import annotations

from app.graph.profiles import get_profile
from app.graph.state import AgentFilmState


def needs_product_confirmation(state: AgentFilmState) -> str:
    """Route based on whether product context needs user confirmation.

    Returns:
      "request_review" if user should confirm product context
      "continue" otherwise (auto-confirmed or already confirmed)
    """
    profile = get_profile(state.get("profile_id", "one-click-quick"))

    # If profile says never confirm, skip
    if not profile.confirm_product_context:
        return "continue"

    # If product context is empty or missing critical fields, ask
    ctx = state.get("product_context", {})
    if not ctx:
        return "request_review"

    # Check for critical fields
    critical_fields = ["product_name", "product_description", "target_audience"]
    missing = [f for f in critical_fields if not ctx.get(f)]
    if missing:
        return "request_review"

    # Check if there's already a pending interaction (avoid duplicate)
    if state.get("pending_interaction"):
        return "continue"

    return "continue"


def review_script_or_storyboard(state: AgentFilmState) -> str:
    """Route based on whether script/storyboard needs user review.

    Returns:
      "request_review" if user should review
      "continue" otherwise
    """
    profile = get_profile(state.get("profile_id", "one-click-quick"))

    if not profile.confirm_script_or_storyboard:
        return "continue"

    script = state.get("script", {})
    storyboard = state.get("storyboard", {})

    if not script and not storyboard:
        return "request_review"

    if state.get("pending_interaction"):
        return "continue"

    return "continue"


def is_terminal(state: AgentFilmState) -> str:
    """Check if the run is in a terminal state."""
    errors = state.get("errors", [])
    retry_count = state.get("retry_count", 0)

    # Cancelled check
    pending_interaction = state.get("pending_interaction")
    if pending_interaction and pending_interaction.get("action") == "cancel":
        return "terminal"

    # Too many errors
    if retry_count > 5:
        return "terminal"

    # Explicit terminal errors
    for err in errors:
        if err.get("fatal"):
            return "terminal"

    return "continue"


def should_retry(state: AgentFilmState) -> str:
    """Determine if we should retry after an error."""
    retry_count = state.get("retry_count", 0)
    max_retries = get_profile(state.get("profile_id", "one-click-quick")).max_graph_retries

    if retry_count < max_retries:
        return "retry"
    return "terminal"
