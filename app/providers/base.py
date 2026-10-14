"""Base Provider abstraction.

All providers (Demo, Real, LLM, Materials, DigitalHuman, Video) implement
this interface. The provider layer is the boundary between the Agent and
external services.

WP-07 provides the abstraction. WP-09 fills in real implementations.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ProviderResult:
    """Standard result from a provider call."""

    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    error_code: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProviderHealth:
    """Health check result for a provider."""

    healthy: bool
    latency_ms: float = 0.0
    message: str = ""


class BaseProvider(ABC):
    """Abstract base for all providers.

    Providers are responsible for:
    - Translating domain requests to external API calls
    - Handling retries, timeouts, and error mapping
    - Respecting rate limits and circuit breakers
    - Never touching the database ORM directly
    """

    def __init__(self, provider_name: str) -> None:
        self.provider_name = provider_name

    @abstractmethod
    async def execute(self, **kwargs: Any) -> ProviderResult:
        """Execute a provider call.

        Args:
            **kwargs: Provider-specific parameters.

        Returns:
            ProviderResult with success flag and data/error.
        """
        raise NotImplementedError

    @abstractmethod
    async def health_check(self) -> ProviderHealth:
        """Check if the provider is available."""
        raise NotImplementedError

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.provider_name!r})"
