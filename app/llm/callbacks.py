"""LangChain callbacks for token counting and cost tracking.

Used to track LLM usage metrics per run for observability and cost control.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from langchain_core.callbacks import BaseCallbackHandler

logger = logging.getLogger(__name__)


class TokenCostCallback(BaseCallbackHandler):
    """Callback that tracks token usage and estimated cost."""

    def __init__(self) -> None:
        super().__init__()
        self.prompt_tokens: int = 0
        self.completion_tokens: int = 0
        self.total_tokens: int = 0
        self.requests: int = 0

    def on_llm_start(self, serialized: dict[str, Any], prompts: list[str], **kwargs: Any) -> None:
        self.requests += 1

    def on_llm_end(self, response: Any, **kwargs: Any) -> None:
        if hasattr(response, "usage") and response.usage:
            usage = response.usage
            self.prompt_tokens += getattr(usage, "prompt_tokens", 0)
            self.completion_tokens += getattr(usage, "completion_tokens", 0)
            self.total_tokens += getattr(usage, "total_tokens", 0)

    def to_dict(self) -> dict[str, Any]:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "requests": self.requests,
        }
