"""Tool Registry: register, lookup, and filter tools by profile.

The registry is the single source of truth for all available tools.
Graph nodes and the Worker use the registry to discover and invoke tools.
"""
from __future__ import annotations

import logging
from typing import Any

from app.tools.contracts import SecurityLevel, ToolContract

logger = logging.getLogger(__name__)

# Known tool names from the frontend Go Client event payloads
KNOWN_TOOL_NAMES: set[str] = {
    "read_file",
    "write_todos",
    "strategy_reference_agent",
    "material_package_curator_agent",
    "read_artifact",
    "creative_rhythm_agent",
    "content_production_agent",
    "post_production_agent",
    "build_final_delivery_from_artifacts",
    "task",
    # Domain tools (WP-08/WP-09)
    "parse_product_link",
    "extract_product_facts",
    "collect_product_materials",
    "generate_creative_strategy",
    "generate_video_script",
    "generate_storyboard",
    "search_materials",
    "select_materials",
    "match_digital_human",
    "generate_voice_script",
    "render_video",
    "validate_video",
    "publish_artifact",
}


class ToolRegistry:
    """Central registry for tool contracts.

    Usage:
        registry = ToolRegistry()
        registry.register(ToolContract(...))
        contract = registry.get("render_video")
        allowed = registry.filter_by_profile("one-click-quick")
    """

    def __init__(self) -> None:
        self._tools: dict[str, ToolContract] = {}

    def register(self, contract: ToolContract) -> None:
        """Register a tool contract. Idempotent: overwrites existing."""
        if contract.name in self._tools:
            logger.warning("Tool %r re-registered", contract.name)
        self._tools[contract.name] = contract
        logger.debug("Tool registered: %s (level=%s)", contract.name, contract.security_level.value)

    def register_many(self, contracts: list[ToolContract]) -> None:
        """Register multiple contracts."""
        for c in contracts:
            self.register(c)

    def get(self, name: str) -> ToolContract | None:
        """Get a tool contract by name."""
        return self._tools.get(name)

    def get_or_raise(self, name: str) -> ToolContract:
        """Get a tool contract by name, raise if not found."""
        tool = self.get(name)
        if tool is None:
            raise KeyError(f"Tool {name!r} not registered. Known tools: {sorted(self._tools)}")
        return tool

    def all(self) -> dict[str, ToolContract]:
        """Return all registered contracts."""
        return dict(self._tools)

    def filter_by_profile(
        self,
        profile_id: str,
        allowed_security_levels: set[SecurityLevel] | None = None,
    ) -> list[ToolContract]:
        """Filter tools available to a profile.

        By default, all tools are available to all profiles.
        Profiles can restrict by security level.
        """
        tools = list(self._tools.values())
        if allowed_security_levels is not None:
            tools = [t for t in tools if t.security_level in allowed_security_levels]
        return tools

    def is_known(self, name: str) -> bool:
        """Check if a tool name is recognized."""
        return name in self._tools or name in KNOWN_TOOL_NAMES


# Global singleton
_registry = ToolRegistry()


def get_registry() -> ToolRegistry:
    """Return the global tool registry."""
    return _registry


def register_default_tools() -> None:
    """Register the default set of domain tools.

    WP-08/WP-09 will call this with actual contracts.
    This function registers placeholder contracts so the registry is never empty.
    """
    defaults = [
        ToolContract(
            name="parse_product_link",
            description="Parse a product link and extract structured data",
            input_schema={"type": "object", "properties": {"url": {"type": "string"}}},
            output_schema={"type": "object"},
            security_level=SecurityLevel.L1,
            provider="research",
        ),
        ToolContract(
            name="extract_product_facts",
            description="Extract product facts from collected data",
            input_schema={"type": "object"},
            output_schema={"type": "object"},
            security_level=SecurityLevel.L0,
            provider="research",
        ),
        ToolContract(
            name="generate_creative_strategy",
            description="Generate marketing creative strategy via LLM",
            input_schema={"type": "object"},
            output_schema={"type": "object"},
            security_level=SecurityLevel.L0,
            provider="llm",
        ),
        ToolContract(
            name="generate_video_script",
            description="Generate video script via LLM",
            input_schema={"type": "object"},
            output_schema={"type": "object"},
            security_level=SecurityLevel.L0,
            provider="llm",
        ),
        ToolContract(
            name="search_materials",
            description="Search for video materials",
            input_schema={"type": "object"},
            output_schema={"type": "object"},
            security_level=SecurityLevel.L1,
            provider="materials",
        ),
        ToolContract(
            name="select_materials",
            description="Select materials from search results",
            input_schema={"type": "object"},
            output_schema={"type": "object"},
            security_level=SecurityLevel.L0,
            provider="materials",
        ),
        ToolContract(
            name="match_digital_human",
            description="Match a digital human to the product/script",
            input_schema={"type": "object"},
            output_schema={"type": "object"},
            security_level=SecurityLevel.L1,
            provider="digital_human",
        ),
        ToolContract(
            name="render_video",
            description="Trigger video rendering (L3: requires approval)",
            input_schema={"type": "object"},
            output_schema={"type": "object"},
            security_level=SecurityLevel.L3,
            approval_requirement=SecurityLevel.L3.value,
            provider="video",
        ),
        ToolContract(
            name="validate_video",
            description="Validate the rendered video output",
            input_schema={"type": "object"},
            output_schema={"type": "object"},
            security_level=SecurityLevel.L0,
            provider="video",
        ),
        ToolContract(
            name="publish_artifact",
            description="Publish final artifacts (L3: requires approval)",
            input_schema={"type": "object"},
            output_schema={"type": "object"},
            security_level=SecurityLevel.L3,
            approval_requirement=SecurityLevel.L3.value,
            provider="artifact",
        ),
    ]
    _registry.register_many(defaults)
