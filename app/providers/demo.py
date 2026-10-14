"""Demo Provider: deterministic, no external API calls.

Used for local development and testing. MUST NOT be loaded in production
environments (enforced by settings.ENABLE_DEMO_PROVIDER and the
Settings.model_validator).
"""
from __future__ import annotations

import logging
from typing import Any

from app.providers.base import BaseProvider, ProviderHealth, ProviderResult
from app.settings import settings

logger = logging.getLogger(__name__)


class DemoProductResearchProvider(BaseProvider):
    """Demo product research — returns deterministic product data."""

    def __init__(self) -> None:
        super().__init__("demo_product_research")
        self._enforce_demo_allowed()

    def _enforce_demo_allowed(self) -> None:
        if not settings.enable_demo_provider:
            raise RuntimeError(
                "DemoProvider is disabled. "
                "Set ENABLE_DEMO_PROVIDER=true or use a non-production environment."
            )

    async def execute(self, **kwargs: Any) -> ProviderResult:
        url = kwargs.get("url", "")
        if "example.com" in url or not url:
            return ProviderResult(
                success=True,
                data={
                    "product_name": "Demo Product",
                    "product_description": "A sample product for demonstration",
                    "target_audience": "General consumers",
                    "key_selling_points": ["Quality", "Price", "Design"],
                    "images": [],
                },
            )
        return ProviderResult(
            success=False,
            error="Demo provider cannot extract real product data. Use a real provider.",
            error_code="demo_limit",
        )

    async def health_check(self) -> ProviderHealth:
        return ProviderHealth(healthy=True, message="Demo provider always healthy")


class DemoMaterialProvider(BaseProvider):
    """Demo material provider — returns deterministic material data."""

    def __init__(self) -> None:
        super().__init__("demo_materials")
        self._enforce_demo_allowed()

    def _enforce_demo_allowed(self) -> None:
        if not settings.enable_demo_provider:
            raise RuntimeError(
                "DemoProvider is disabled. "
                "Set ENABLE_DEMO_PROVIDER=true or use a non-production environment."
            )

    async def execute(self, **kwargs: Any) -> ProviderResult:
        query = kwargs.get("query", "")
        return ProviderResult(
            success=True,
            data={
                "materials": [
                    {
                        "id": f"demo-mat-{i}",
                        "name": f"Demo Material {i}",
                        "type": "image",
                        "url": f"https://example.com/material-{i}.jpg",
                        "preview_url": f"https://example.com/material-{i}-preview.jpg",
                    }
                    for i in range(1, 4)
                ],
                "query": query,
            },
        )

    async def health_check(self) -> ProviderHealth:
        return ProviderHealth(healthy=True, message="Demo provider always healthy")


class DemoDigitalHumanProvider(BaseProvider):
    """Demo digital human provider — returns deterministic avatar data."""

    def __init__(self) -> None:
        super().__init__("demo_digital_human")
        self._enforce_demo_allowed()

    def _enforce_demo_allowed(self) -> None:
        if not settings.enable_demo_provider:
            raise RuntimeError(
                "DemoProvider is disabled. "
                "Set ENABLE_DEMO_PROVIDER=true or use a non-production environment."
            )

    async def execute(self, **kwargs: Any) -> ProviderResult:
        return ProviderResult(
            success=True,
            data={
                "digital_human_id": "demo-avatar-001",
                "name": "Demo Avatar",
                "avatar_url": "https://example.com/avatar.png",
                "voice_id": "demo-voice-001",
                "gender": "neutral",
                "style": "professional",
            },
        )

    async def health_check(self) -> ProviderHealth:
        return ProviderHealth(healthy=True, message="Demo provider always healthy")


class DemoVideoRenderProvider(BaseProvider):
    """Demo video render provider — returns deterministic video data."""

    def __init__(self) -> None:
        super().__init__("demo_video_render")
        self._enforce_demo_allowed()

    def _enforce_demo_allowed(self) -> None:
        if not settings.enable_demo_provider:
            raise RuntimeError(
                "DemoProvider is disabled. "
                "Set ENABLE_DEMO_PROVIDER=true or use a non-production environment."
            )

    async def execute(self, **kwargs: Any) -> ProviderResult:
        script = kwargs.get("script", {})
        aspect_ratio = kwargs.get("aspect_ratio", "16:9")
        duration = kwargs.get("duration_seconds", 30)

        return ProviderResult(
            success=True,
            data={
                "video_url": "https://example.com/demo-video.mp4",
                "cover_url": "https://example.com/demo-cover.jpg",
                "duration_seconds": duration,
                "aspect_ratio": aspect_ratio,
                "format": "mp4",
                "resolution": "1920x1080",
                "script_sections": len(script.get("segments", [])),
            },
            metadata={"provider": "demo", "simulated": True},
        )

    async def health_check(self) -> ProviderHealth:
        return ProviderHealth(healthy=True, message="Demo provider always healthy")


# ---------------------------------------------------------------------------
# Provider factory
# ---------------------------------------------------------------------------


def create_demo_provider(provider_type: str) -> BaseProvider:
    """Create a demo provider by type.

    Args:
        provider_type: One of "product_research", "materials",
                       "digital_human", "video_render".

    Returns:
        A demo provider instance.

    Raises:
        ValueError: If provider_type is unknown.
        RuntimeError: If demo provider is disabled in settings.
    """
    providers = {
        "product_research": DemoProductResearchProvider,
        "materials": DemoMaterialProvider,
        "digital_human": DemoDigitalHumanProvider,
        "video_render": DemoVideoRenderProvider,
    }
    cls = providers.get(provider_type)
    if cls is None:
        raise ValueError(
            f"Unknown demo provider type: {provider_type!r}. "
            f"Known types: {sorted(providers)}"
        )
    return cls()


def is_demo_provider_enabled() -> bool:
    """Check if demo providers are allowed in the current configuration."""
    return settings.enable_demo_provider
