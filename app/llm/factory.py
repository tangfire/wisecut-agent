"""LLM provider factory.

Supports:
  - Demo LLM: deterministic, no external API calls
  - OpenAI-compatible: any OpenAI-compatible API endpoint

The factory reads settings.llm_provider to determine which provider to use.
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI

from app.settings import settings

logger = logging.getLogger(__name__)


class DemoLLM(BaseChatModel):
    """Demo LLM that returns deterministic responses.

    Used for local development and testing without external API calls.
    """

    model_name: str = "demo"
    temperature: float = 0.7

    def _generate(self, prompts, **kwargs: Any) -> Any:
        # Demo: return a simple response
        from langchain_core.messages import AIMessage
        return AIMessage(content="[DEMO] This is a deterministic demo response.")

    @property
    def _llm_type(self) -> str:
        return "demo"

    def _call(self, prompt: str, **kwargs: Any) -> str:
        return "[DEMO] This is a deterministic demo response."


def create_llm(provider: str | None = None, **kwargs: Any) -> BaseChatModel:
    """Create an LLM instance based on the provider setting.

    Args:
        provider: One of "demo", "openai-compatible". Falls back to settings.llm_provider.
        **kwargs: Override settings (model, temperature, etc.)

    Returns:
        A LangChain BaseChatModel instance.
    """
    provider = provider or settings.llm_provider

    if provider == "demo":
        return DemoLLM(
            model_name=kwargs.get("model", settings.llm_model),
            temperature=kwargs.get("temperature", settings.llm_temperature),
        )

    if provider == "openai-compatible":
        return ChatOpenAI(
            model=kwargs.get("model", settings.llm_model),
            temperature=kwargs.get("temperature", settings.llm_temperature),
            max_tokens=kwargs.get("max_tokens", settings.llm_max_tokens),
            api_key=kwargs.get("api_key", settings.llm_api_key or "sk-demo"),
            base_url=kwargs.get("base_url", settings.llm_base_url or "http://localhost:8000/v1"),
        )

    raise ValueError(f"Unknown LLM provider: {provider}. Must be 'demo' or 'openai-compatible'.")


def get_default_llm() -> BaseChatModel:
    """Get the default LLM from settings."""
    return create_llm()
