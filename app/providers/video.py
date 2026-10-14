"""Video Render Provider.

Renders the final video from script, materials, and digital human.

WP-07: interface + demo implementation.
WP-09: real implementation connects to video rendering service.
"""
from __future__ import annotations

from typing import Any

from app.providers.base import BaseProvider, ProviderHealth, ProviderResult
from app.providers.demo import DemoVideoRenderProvider, is_demo_provider_enabled


class VideoRenderProvider:
    """Wrapper that selects demo or real video render provider."""

    def __init__(self) -> None:
        self._provider: BaseProvider
        if is_demo_provider_enabled():
            self._provider = DemoVideoRenderProvider()
        else:
            self._provider = _RealVideoRenderProvider()

    async def execute(self, **kwargs: Any) -> ProviderResult:
        return await self._provider.execute(**kwargs)

    async def health_check(self) -> ProviderHealth:
        return await self._provider.health_check()


class _RealVideoRenderProvider(BaseProvider):
    """Real video render provider (WP-09 implementation)."""

    def __init__(self) -> None:
        super().__init__("real_video_render")

    async def execute(self, **kwargs: Any) -> ProviderResult:
        return ProviderResult(
            success=False,
            error="Real video render provider not yet implemented (WP-09)",
            error_code="not_implemented",
        )

    async def health_check(self) -> ProviderHealth:
        return ProviderHealth(healthy=False, message="Real provider not implemented")
