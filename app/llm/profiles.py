"""Prompt profiles: versioned prompts for each graph node.

Each prompt profile includes:
  - prompt_name: identifier for the prompt
  - prompt_version: semantic version
  - system_prompt: the system prompt text
  - user_prompt_template: Jinja2-style template for user prompt
  - output_schema_version: version of the expected output schema
  - model_provider: which LLM provider to use
  - model_name: which model to use
  - temperature: sampling temperature
  - max_tokens: max output tokens

WP-06 provides the registry structure.  WP-08 fills in actual prompts.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PromptProfile:
    """Versioned prompt configuration."""

    prompt_name: str
    prompt_version: str
    system_prompt: str
    user_prompt_template: str
    output_schema_version: str = "1.0"
    model_provider: str = "demo"
    model_name: str = "gpt-4o-mini"
    temperature: float = 0.7
    max_tokens: int = 4096


# ---------------------------------------------------------------------------
# Default prompt profiles (WP-08 will replace with real prompts)
# ---------------------------------------------------------------------------

PRODUCT_CONTEXT_PROMPT = PromptProfile(
    prompt_name="collect_product_context",
    prompt_version="1.0.0",
    system_prompt="You are a product information extraction assistant.",
    user_prompt_template="Extract product information from: {user_request}\nLink: {product_link}",
    output_schema_version="1.0",
)

CREATIVE_STRATEGY_PROMPT = PromptProfile(
    prompt_name="generate_creative_strategy",
    prompt_version="1.0.0",
    system_prompt="You are a marketing creative strategist.",
    user_prompt_template="Generate a creative strategy for: {product_context}\nTarget: {language}",
    output_schema_version="1.0",
)

SCRIPT_PROMPT = PromptProfile(
    prompt_name="generate_script",
    prompt_version="1.0.0",
    system_prompt="You are a video script writer.",
    user_prompt_template="Generate a video script based on: {creative_strategy}",
    output_schema_version="1.0",
)

PROMPT_REGISTRY: dict[str, PromptProfile] = {
    p.prompt_name: p for p in [
        PRODUCT_CONTEXT_PROMPT,
        CREATIVE_STRATEGY_PROMPT,
        SCRIPT_PROMPT,
    ]
}


def get_prompt_profile(prompt_name: str) -> PromptProfile:
    """Get a prompt profile by name."""
    return PROMPT_REGISTRY.get(prompt_name, PRODUCT_CONTEXT_PROMPT)
