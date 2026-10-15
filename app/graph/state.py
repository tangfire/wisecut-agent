"""AgentFilmState: the TypedDict that flows through the LangGraph StateGraph.

All state updates happen through explicit node outputs.  Tools and nodes
MUST NOT mutate global state directly.

Design (plan.md §6):
  - conversation_id, run_id, profile_id, language: identity
  - user_request, product_link, input_files: user input
  - product_context, creative_strategy, script, storyboard: pipeline data
  - materials, digital_human, render_job, artifacts: media data
  - pending_interaction, pending_approval: HITL state
  - errors, retry_count: error tracking
"""

from __future__ import annotations

from typing import Any, TypedDict


class AgentFilmState(TypedDict):
    """Complete state for a single Agent Film run."""

    # Identity
    conversation_id: str
    run_id: str
    profile_id: str
    language: str

    # User input
    user_request: str
    product_link: str | None
    input_files: list[dict[str, Any]]

    # Pipeline data
    product_context: dict[str, Any]
    creative_strategy: dict[str, Any]
    script: dict[str, Any]
    storyboard: dict[str, Any]

    # Media data
    materials: list[dict[str, Any]]
    digital_human: dict[str, Any] | None
    render_job: dict[str, Any] | None
    artifacts: list[dict[str, Any]]

    # HITL state
    pending_interaction: dict[str, Any] | None
    pending_approval: dict[str, Any] | None

    # Error tracking
    errors: list[dict[str, Any]]
    retry_count: int


def create_initial_state(
    conversation_id: str,
    run_id: str,
    profile_id: str = "one-click-quick",
    language: str = "zh-CN",
    user_request: str = "",
    product_link: str | None = None,
    input_files: list[dict[str, Any]] | None = None,
) -> AgentFilmState:
    """Create a fresh AgentFilmState with sensible defaults."""
    return AgentFilmState(
        conversation_id=conversation_id,
        run_id=run_id,
        profile_id=profile_id,
        language=language,
        user_request=user_request,
        product_link=product_link,
        input_files=input_files or [],
        product_context={},
        creative_strategy={},
        script={},
        storyboard={},
        materials=[],
        digital_human=None,
        render_job=None,
        artifacts=[],
        pending_interaction=None,
        pending_approval=None,
        errors=[],
        retry_count=0,
    )
