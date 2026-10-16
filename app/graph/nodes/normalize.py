"""Normalize input node: validates and normalizes user input.

Uses domain logic from app.domain.agent_film for actual normalization.
"""
from __future__ import annotations

from typing import Any, cast

from app.domain.agent_film import normalize_start_input


async def normalize_input(state: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize user input.

    Delegates to domain logic which:
      - Trims whitespace
      - Normalizes product_link (adds https:// if missing)
      - Splits files into documents vs materials
      - Builds MAA start message content
    """
    return normalize_start_input(cast(Any, state))
