"""Product Research Provider.

Researches product information from a URL or uploaded files.

WP-07: interface + demo implementation.
WP-09: real implementation connects to actual product research APIs.
"""
from __future__ import annotations

from typing import Any

from app.providers.base import BaseProvider, ProviderHealth, ProviderResult
from app.providers.demo import DemoProductResearchProvider, is_demo_provider_enabled

logger = __name__


class ProductResearchProvider:
    """Wrapper that selects demo or real product research provider.

    Usage:
        provider = ProductResearchProvider()
        result = await provider.execute(url="https://example.com/product")
    """

    def __init__(self) -> None:
        self._provider: BaseProvider
        if is_demo_provider_enabled():
            self._provider = DemoProductResearchProvider()
        else:
            # Real provider will be connected in WP-09
            self._provider = _RealProductResearchProvider()

    async def execute(self, **kwargs: Any) -> ProviderResult:
        return await self._provider.execute(**kwargs)

    async def health_check(self) -> ProviderHealth:
        return await self._provider.health_check()


class _RealProductResearchProvider(BaseProvider):
    """Real product research provider (WP-09 implementation)."""

    def __init__(self) -> None:
        super().__init__("real_product_research")

    async def execute(self, **kwargs: Any) -> ProviderResult:
        return ProviderResult(
            success=False,
            error="Real product research provider not yet implemented (WP-09)",
            error_code="not_implemented",
        )

    async def health_check(self) -> ProviderHealth:
        return ProviderHealth(healthy=False, message="Real provider not implemented")
