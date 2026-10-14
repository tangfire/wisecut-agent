"""Normalize input node: validates and normalizes user input."""

from __future__ import annotations

from app.graph.state import AgentFilmState


async def normalize_input(state: AgentFilmState) -> dict[str, Any]:
    """Validate and normalize user input.

    - Trim whitespace from user_request
    - Normalize product_link (strip query params if present)
    - Ensure input_files is a list of dicts
    """
    user_request = (state.get("user_request") or "").strip()
    product_link = state.get("product_link")
    if product_link:
        product_link = product_link.strip().split("?")[0]  # Remove query params for now
    input_files = state.get("input_files") or []
    if not isinstance(input_files, list):
        input_files = []

    return {
        "user_request": user_request,
        "product_link": product_link,
        "input_files": input_files,
    }
