"""Digital Human Provider.

Matches and selects digital human avatars for videos.

WP-07: interface + demo implementation.
WP-09: real implementation connects to digital human service.
"""
from __future__ import annotations

from typing import Any

from app.providers.base import BaseProvider, ProviderHealth, ProviderResult
from app.providers.demo import DemoDigitalHumanProvider, is_demo_provider_enabled


class DigitalHumanProvider:
    """Wrapper that selects demo or real digital human provider."""

    def __init__(self) -> None:
        self._provider: BaseProvider
        if is_demo_provider_enabled():
            self._provider = DemoDigitalHumanProvider()
        else:
            self._provider = _RealDigitalHumanProvider()

    async def execute(self, **kwargs: Any) -> ProviderResult:
        return await self._provider.execute(**kwargs)

    async def health_check(self) -> ProviderHealth:
        return await self._provider.health_check()


class _RealDigitalHumanProvider(BaseProvider):
    """Real digital human provider (WP-09 implementation)."""

    def __init__(self) -> None:
        super().__init__("real_digital_human")

    async def execute(self, **kwargs: Any) -> ProviderResult:
        return ProviderResult(
            success=False,
            error="Real digital human provider not yet implemented (WP-09)",
            error_code="not_implemented",
        )

    async def health_check(self) -> ProviderHealth:
        return ProviderHealth(healthy=False, message="Real provider not implemented")
