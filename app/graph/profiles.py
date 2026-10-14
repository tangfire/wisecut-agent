"""Profile configurations for Agent Film.

Each profile defines:
  - profile_id: the MAA profile identifier (e.g., one-click-quick, one-click-cocreate)
  - mode: quick | deep
  - interaction_strategy: which HITL checkpoints to show
  - default_video_params: aspect ratio, duration, etc.
  - retry_policy: max retries for tools and LLM
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class AgentProfile:
    """Immutable profile configuration."""

    profile_id: str
    mode: str  # "quick" or "deep"
    display_name: str
    description: str

    # Interaction strategy
    confirm_product_context: bool = True
    confirm_script_or_storyboard: bool = True
    confirm_generation_start: bool = True

    # Defaults
    default_aspect_ratio: str = "16:9"
    default_duration: str = "30s"
    default_language: str = "zh-CN"

    # Retry limits
    max_tool_retries: int = 3
    max_llm_retries: int = 2
    max_graph_retries: int = 1


# Quick profile: minimal interaction, auto-confirm wherever possible
QUICK_PROFILE = AgentProfile(
    profile_id="one-click-quick",
    mode="quick",
    display_name="Quick Generate",
    description="One-click video generation with minimal user interaction.",
    confirm_product_context=False,  # Auto-extract, only ask if critical fields missing
    confirm_script_or_storyboard=False,  # Auto-generate script/storyboard
    confirm_generation_start=True,  # Always confirm before rendering (cost guard)
    max_tool_retries=2,
    max_llm_retries=2,
)

# Deep profile: full HITL, user controls every major step
DEEP_PROFILE = AgentProfile(
    profile_id="one-click-cocreate",
    mode="deep",
    display_name="Co-create",
    description="Full co-creation mode with user approval at every step.",
    confirm_product_context=True,
    confirm_script_or_storyboard=True,
    confirm_generation_start=True,
    max_tool_retries=3,
    max_llm_retries=3,
)

PROFILE_MAP: dict[str, AgentProfile] = {
    p.profile_id: p for p in [QUICK_PROFILE, DEEP_PROFILE]
}


def get_profile(profile_id: str) -> AgentProfile:
    """Get profile by ID, falling back to QUICK_PROFILE."""
    return PROFILE_MAP.get(profile_id, QUICK_PROFILE)


def profile_id_to_mode(profile_id: str | None) -> str:
    """Convert profile_id to mode string for MAA metadata."""
    profile = get_profile(profile_id or "one-click-quick")
    return profile.mode
