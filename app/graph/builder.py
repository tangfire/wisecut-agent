"""LangGraph StateGraph builder for Agent Film.

The graph defines the execution flow:
  START
    ↓
  normalize_input
    ↓
  collect_product_context
    ↓
  [conditional] needs_product_confirmation?
    ├─ request_review → request_product_context_review (interrupt)
    └─ continue → generate_creative_strategy
                      ↓
                  generate_script
                      ↓
                  [conditional] review_script_or_storyboard?
                    ├─ request_review → request_storyboard_review (interrupt)
                    └─ continue → prepare_generation
                                      ↓
                                  request_generation_approval (interrupt)
                                      ↓
                                  collect_materials
                                      ↓
                                  match_digital_human
                                      ↓
                                  render_video
                                      ↓
                                  validate_delivery
                                      ↓
                                  publish_artifacts
                                      ↓
                                  END

WP-06 implements:
  - StateGraph construction
  - Node registration (stubs for WP-08/WP-09 to fill in)
  - Interrupt/resume binding
  - Thread ID <-> Run ID mapping
  - Profile-specific routing
  - Event emission hooks
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Coroutine
from typing import Any, cast

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, StateGraph

from app.graph.routing import (
    is_terminal,
    needs_product_confirmation,
    review_script_or_storyboard,
)
from app.graph.state import AgentFilmState

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Node type definition
# ---------------------------------------------------------------------------

# A node function takes the full AgentFilmState and returns a partial update
NodeFunc = Callable[[AgentFilmState], Coroutine[Any, Any, dict[str, Any]]]


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------


class AgentFilmGraphBuilder:
    """Builds and configures the Agent Film StateGraph.

    Usage:
        builder = AgentFilmGraphBuilder(checkpointer=checkpointer)
        graph = builder.build()
        app = graph.compile()
    """

    def __init__(
        self,
        checkpointer: BaseCheckpointSaver[Any] | None = None,
        default_profile_id: str = "one-click-quick",
    ) -> None:
        self._checkpointer = checkpointer
        self._default_profile = default_profile_id
        self._graph: StateGraph = StateGraph(AgentFilmState)
        self._nodes: dict[str, NodeFunc] = {}
        self._interrupt_nodes: set[str] = set()

    # ------------------------------------------------------------------
    # Node registration
    # ------------------------------------------------------------------

    def add_node(
        self,
        name: str,
        func: NodeFunc,
        interrupt: bool = False,
    ) -> AgentFilmGraphBuilder:
        """Register a graph node.

        Args:
            name: Node name (used in routing).
            func: Async function that takes state and returns state update dict.
            interrupt: If True, the graph will pause here and wait for resume.
        """
        self._nodes[name] = func
        self._graph.add_node(name, self._wrap_node(func))
        if interrupt:
            self._interrupt_nodes.add(name)
        return self

    def _wrap_node(self, func: NodeFunc) -> NodeFunc:
        """Wrap a node to add logging and error handling."""
        async def wrapper(state: AgentFilmState) -> dict[str, Any]:
            node_name = func.__name__
            run_id = state.get("run_id", "?")
            try:
                logger.info(
                    "Graph node started",
                    extra={"node": node_name, "run_id": run_id},
                )
                update = await func(state)
                logger.info(
                    "Graph node completed",
                    extra={"node": node_name, "run_id": run_id},
                )
                return update
            except Exception as exc:
                logger.error(
                    "Graph node failed",
                    extra={"node": node_name, "run_id": run_id, "error": str(exc)},
                )
                errors = state.get("errors", []) + [
                    {"node": node_name, "error": str(exc), "fatal": False}
                ]
                return {"errors": errors, "retry_count": state.get("retry_count", 0) + 1}
        return wrapper

    # ------------------------------------------------------------------
    # Edge registration
    # ------------------------------------------------------------------

    def add_edge(self, start: str, end: str) -> AgentFilmGraphBuilder:
        """Add a direct edge from start to end."""
        self._graph.add_edge(start, end)
        return self

    def add_conditional_edges(
        self,
        source: str,
        router: Callable[[AgentFilmState], str],
        route_map: dict[str, str],
    ) -> AgentFilmGraphBuilder:
        """Add conditional edges from source based on router function."""
        self._graph.add_conditional_edges(  # type: ignore[arg-type]
            source, router, cast("dict[Any, str]", route_map)
        )
        return self

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def build(self) -> StateGraph:
        """Construct the complete Agent Film graph.

        Nodes (WP-06 stubs, implemented in WP-07/WP-08):
          - normalize_input: validate and normalize user input
          - collect_product_context: extract product info from link/files
          - request_product_context_review: emit interaction.requested and pause
          - generate_creative_strategy: LLM generates marketing strategy
          - generate_script: LLM generates video script
          - request_storyboard_review: emit interaction.requested and pause
          - prepare_generation: prepare materials and settings
          - request_generation_approval: emit approval.required and pause
          - collect_materials: search/select materials (WP-09)
          - match_digital_human: match digital human (WP-09)
          - render_video: trigger video rendering (WP-09)
          - validate_delivery: validate video output (WP-09)
          - publish_artifacts: publish final artifacts (WP-09)
        """
        g = self._graph

        # Entry point
        g.set_entry_point("normalize_input")

        # Main flow
        g.add_edge("normalize_input", "collect_product_context")
        g.add_conditional_edges(
            "collect_product_context",
            needs_product_confirmation,
            {
                "request_review": "request_product_context_review",
                "continue": "generate_creative_strategy",
            },
        )

        # Interrupt: product context review
        g.add_edge("request_product_context_review", END)

        # Script generation flow
        g.add_edge("generate_creative_strategy", "generate_script")
        g.add_conditional_edges(
            "generate_script",
            review_script_or_storyboard,
            {
                "request_review": "request_storyboard_review",
                "continue": "prepare_generation",
            },
        )

        # Interrupt: storyboard review
        g.add_edge("request_storyboard_review", END)

        # Generation flow
        g.add_edge("prepare_generation", "request_generation_approval")

        # Interrupt: generation approval
        g.add_edge("request_generation_approval", END)

        # Media pipeline (WP-09 fills in actual implementations)
        g.add_edge("collect_materials", "match_digital_human")
        g.add_edge("match_digital_human", "render_video")
        g.add_edge("render_video", "validate_delivery")
        g.add_edge("validate_delivery", "publish_artifacts")
        g.add_edge("publish_artifacts", END)

        # Error handling
        g.add_conditional_edges(
            "publish_artifacts",
            is_terminal,
            {"terminal": END, "continue": "publish_artifacts"},
        )

        return g

    def compile(self) -> Any:
        """Build and compile the graph.

        Returns a compiled LangGraph application ready for execution.
        """
        graph = self.build()
        return graph.compile(checkpointer=self._checkpointer)


# ---------------------------------------------------------------------------
# Default node implementations (WP-08: real business logic)
# ---------------------------------------------------------------------------


async def normalize_input(state: AgentFilmState) -> dict[str, Any]:
    """Validate and normalize user input.

    Delegates to domain logic:
      - normalize_start_input from app.domain.agent_film
    """
    from app.graph.nodes.normalize import normalize_input as _normalize
    return await _normalize(state)


async def collect_product_context(state: AgentFilmState) -> dict[str, Any]:
    """Extract product context from link and files.

    Delegates to domain logic:
      - extract_product_context from app.domain.agent_film
    """
    from app.graph.nodes.product_context import collect_product_context as _collect
    return await _collect(state)


async def request_product_context_review(state: AgentFilmState) -> dict[str, Any]:
    """Emit interaction.requested for product context confirmation.

    Returns a confirm_extracted_product_context interaction payload.
    """
    from app.graph.nodes.product_context import request_product_context_review as _review
    return await _review(state)


async def generate_creative_strategy(state: AgentFilmState) -> dict[str, Any]:
    """Generate marketing creative strategy.

    Delegates to domain logic:
      - generate_creative_strategy from app.domain.agent_film
    """
    from app.graph.nodes.script import generate_creative_strategy_node as _gen
    return await _gen(state)


async def generate_script(state: AgentFilmState) -> dict[str, Any]:
    """Generate video script.

    Delegates to domain logic:
      - generate_script from app.domain.agent_film
    """
    from app.graph.nodes.script import generate_script_node as _gen
    return await _gen(state)


async def request_storyboard_review(state: AgentFilmState) -> dict[str, Any]:
    """Emit storyboard review interaction and pause.

    Returns a review_storyboard_script interaction payload.
    """
    from app.graph.nodes.script import request_storyboard_review_node as _review
    return await _review(state)


async def prepare_generation(state: AgentFilmState) -> dict[str, Any]:
    """Prepare materials and settings for generation.

    Delegates to domain logic:
      - prepare_generation from app.domain.agent_film
    """
    from app.graph.nodes.generation import prepare_generation_node as _prepare
    return await _prepare(state)


async def request_generation_approval(state: AgentFilmState) -> dict[str, Any]:
    """Emit approval.required for generation start.

    Returns a confirm_generation_start approval payload with cost breakdown.
    """
    from app.graph.nodes.generation import request_generation_approval_node as _approve
    return await _approve(state)


async def collect_materials(state: AgentFilmState) -> dict[str, Any]:
    """Search and select materials.

    WP-09: delegates to select_materials_for_render.
    """
    from app.graph.nodes.media import collect_materials as _collect
    return await _collect(state)


async def match_digital_human(state: AgentFilmState) -> dict[str, Any]:
    """Match digital human to product/script.

    WP-09: delegates to match_digital_human_node.
    """
    from app.graph.nodes.media import match_digital_human_node as _match
    return await _match(state)


async def render_video(state: AgentFilmState) -> dict[str, Any]:
    """Trigger video rendering.

    WP-09: delegates to render_video_node.
    """
    from app.graph.nodes.media import render_video_node as _render
    return await _render(state)


async def validate_delivery(state: AgentFilmState) -> dict[str, Any]:
    """Validate rendered video.

    WP-09: delegates to validate_delivery_node.
    """
    from app.graph.nodes.media import validate_delivery_node as _validate
    return await _validate(state)


async def publish_artifacts(state: AgentFilmState) -> dict[str, Any]:
    """Publish final artifacts.

    WP-09: delegates to publish_artifacts_node.
    """
    from app.graph.nodes.media import publish_artifacts_node as _publish
    return await _publish(state)


# ---------------------------------------------------------------------------
# Helper: build the default graph
# ---------------------------------------------------------------------------


def build_default_graph(
    checkpointer: BaseCheckpointSaver[Any] | None = None,
    profile_id: str = "one-click-quick",
) -> Any:
    """Build the default Agent Film graph with stub nodes.

    WP-06 provides the infrastructure.  WP-08/WP-09 replace the stubs
    with real implementations.
    """
    builder = AgentFilmGraphBuilder(
        checkpointer=checkpointer,
        default_profile_id=profile_id,
    )

    # Register all nodes
    builder.add_node("normalize_input", normalize_input)
    builder.add_node("collect_product_context", collect_product_context)
    builder.add_node("request_product_context_review", request_product_context_review, interrupt=True)
    builder.add_node("generate_creative_strategy", generate_creative_strategy)
    builder.add_node("generate_script", generate_script)
    builder.add_node("request_storyboard_review", request_storyboard_review, interrupt=True)
    builder.add_node("prepare_generation", prepare_generation)
    builder.add_node("request_generation_approval", request_generation_approval, interrupt=True)
    builder.add_node("collect_materials", collect_materials)
    builder.add_node("match_digital_human", match_digital_human)
    builder.add_node("render_video", render_video)
    builder.add_node("validate_delivery", validate_delivery)
    builder.add_node("publish_artifacts", publish_artifacts)

    return builder.compile()
