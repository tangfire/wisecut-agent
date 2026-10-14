"""Material Provider.

Searches and selects video materials (images, audio, video clips).

WP-07: interface + demo implementation.
WP-09: real implementation connects to material libraries.
"""
from __future__ import annotations

from typing import Any

from app.providers.base import BaseProvider, ProviderHealth, ProviderResult
from app.providers.demo import DemoMaterialProvider, is_demo_provider_enabled


class MaterialProvider:
    """Wrapper that selects demo or real material provider."""

    def __init__(self) -> None:
        self._provider: BaseProvider
        if is_demo_provider_enabled():
            self._provider = DemoMaterialProvider()
        else:
            self._provider = _RealMaterialProvider()

    async def execute(self, **kwargs: Any) -> ProviderResult:
        return await self._provider.execute(**kwargs)

    async def health_check(self) -> ProviderHealth:
        return await self._provider.health_check()


class _RealMaterialProvider(BaseProvider):
    """Real material provider (WP-09 implementation)."""

    def __init__(self) -> None:
        super().__init__("real_materials")

    async def execute(self, **kwargs: Any) -> ProviderResult:
        return ProviderResult(
            success=False,
            error="Real material provider not yet implemented (WP-09)",
            error_code="not_implemented",
        )

    async def health_check(self) -> ProviderHealth:
        return ProviderHealth(healthy=False, message="Real provider not implemented")
