"""Providers package: base provider and domain-specific providers."""
from app.providers.base import BaseProvider, ProviderHealth, ProviderResult
from app.providers.demo import (
    DemoDigitalHumanProvider,
    DemoMaterialProvider,
    DemoProductResearchProvider,
    DemoVideoRenderProvider,
    create_demo_provider,
    is_demo_provider_enabled,
)
from app.providers.digital_human import DigitalHumanProvider
from app.providers.materials import MaterialProvider
from app.providers.research import ProductResearchProvider
from app.providers.video import VideoRenderProvider

__all__ = [
    # Base
    "BaseProvider",
    "ProviderHealth",
    "ProviderResult",
    # Demo
    "DemoProductResearchProvider",
    "DemoMaterialProvider",
    "DemoDigitalHumanProvider",
    "DemoVideoRenderProvider",
    "create_demo_provider",
    "is_demo_provider_enabled",
    # Domain
    "ProductResearchProvider",
    "MaterialProvider",
    "DigitalHumanProvider",
    "VideoRenderProvider",
]
