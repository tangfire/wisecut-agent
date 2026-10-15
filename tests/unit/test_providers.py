"""Unit tests for WP-07 Provider platform.

Covers:
  - BaseProvider abstract interface
  - DemoProvider factory (demo types)
  - Production protection (demo provider disabled in production)
  - Domain provider wrappers (research, materials, digital_human, video)
"""
from __future__ import annotations

import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


# ---------------------------------------------------------------------------
# BaseProvider tests
# ---------------------------------------------------------------------------


class TestBaseProvider:
    def test_cannot_instantiate_abstract(self):
        from app.providers.base import BaseProvider

        with pytest.raises(TypeError):
            BaseProvider("test")

    def test_subclass_must_implement_execute(self):
        from app.providers.base import BaseProvider

        class IncompleteProvider(BaseProvider):
            async def health_check(self):
                pass

        with pytest.raises(TypeError):
            IncompleteProvider("test")

    def test_subclass_must_implement_health_check(self):
        from app.providers.base import BaseProvider, ProviderResult

        class IncompleteProvider(BaseProvider):
            async def execute(self, **kwargs):
                return ProviderResult(success=True)

        with pytest.raises(TypeError):
            IncompleteProvider("test")

    def test_complete_provider(self):
        from app.providers.base import BaseProvider, ProviderHealth, ProviderResult

        class CompleteProvider(BaseProvider):
            async def execute(self, **kwargs):
                return ProviderResult(success=True)

            async def health_check(self):
                return ProviderHealth(healthy=True)

        provider = CompleteProvider("complete")
        assert provider.provider_name == "complete"


# ---------------------------------------------------------------------------
# DemoProvider tests
# ---------------------------------------------------------------------------


class TestDemoProductResearchProvider:
    @pytest.mark.asyncio
    async def test_execute_with_url(self):
        from app.providers.demo import DemoProductResearchProvider

        provider = DemoProductResearchProvider()
        result = await provider.execute(url="https://example.com/product")
        assert result.success is True
        assert "product_name" in result.data
        assert result.data["product_name"] == "Demo Product"

    @pytest.mark.asyncio
    async def test_execute_without_url(self):
        from app.providers.demo import DemoProductResearchProvider

        provider = DemoProductResearchProvider()
        result = await provider.execute(url="")
        assert result.success is True
        assert "product_name" in result.data

    @pytest.mark.asyncio
    async def test_health_check(self):
        from app.providers.demo import DemoProductResearchProvider

        provider = DemoProductResearchProvider()
        health = await provider.health_check()
        assert health.healthy is True

    def test_disabled_in_production(self):
        from app.providers.demo import DemoProductResearchProvider

        with patch("app.providers.demo.settings") as mock_settings:
            mock_settings.enable_demo_provider = False
            with pytest.raises(RuntimeError, match="DemoProvider is disabled"):
                DemoProductResearchProvider()


class TestDemoMaterialProvider:
    @pytest.mark.asyncio
    async def test_execute_returns_materials(self):
        from app.providers.demo import DemoMaterialProvider

        provider = DemoMaterialProvider()
        result = await provider.execute(query="test")
        assert result.success is True
        assert len(result.data["materials"]) == 3
        assert result.data["materials"][0]["id"] == "demo-mat-1"

    @pytest.mark.asyncio
    async def test_disabled_in_production(self):
        from app.providers.demo import DemoMaterialProvider

        with patch("app.providers.demo.settings") as mock_settings:
            mock_settings.enable_demo_provider = False
            with pytest.raises(RuntimeError, match="DemoProvider is disabled"):
                DemoMaterialProvider()


class TestDemoDigitalHumanProvider:
    @pytest.mark.asyncio
    async def test_execute_returns_avatar(self):
        from app.providers.demo import DemoDigitalHumanProvider

        provider = DemoDigitalHumanProvider()
        result = await provider.execute()
        assert result.success is True
        assert result.data["digital_human_id"] == "demo-avatar-001"

    @pytest.mark.asyncio
    async def test_disabled_in_production(self):
        from app.providers.demo import DemoDigitalHumanProvider

        with patch("app.providers.demo.settings") as mock_settings:
            mock_settings.enable_demo_provider = False
            with pytest.raises(RuntimeError, match="DemoProvider is disabled"):
                DemoDigitalHumanProvider()


class TestDemoVideoRenderProvider:
    @pytest.mark.asyncio
    async def test_execute_returns_video(self):
        from app.providers.demo import DemoVideoRenderProvider

        provider = DemoVideoRenderProvider()
        result = await provider.execute(
            aspect_ratio="16:9",
            duration_seconds=30,
            script={"segments": [{"duration": 10}]},
        )
        assert result.success is True
        assert result.data["video_url"] == "https://example.com/demo-video.mp4"
        assert result.data["aspect_ratio"] == "16:9"
        assert result.data["duration_seconds"] == 30

    @pytest.mark.asyncio
    async def test_disabled_in_production(self):
        from app.providers.demo import DemoVideoRenderProvider

        with patch("app.providers.demo.settings") as mock_settings:
            mock_settings.enable_demo_provider = False
            with pytest.raises(RuntimeError, match="DemoProvider is disabled"):
                DemoVideoRenderProvider()


class TestDemoProviderFactory:
    def test_create_product_research(self):
        from app.providers.demo import create_demo_provider

        with patch("app.providers.demo.settings") as mock_settings:
            mock_settings.enable_demo_provider = True
            provider = create_demo_provider("product_research")
            assert provider.provider_name == "demo_product_research"

    def test_create_materials(self):
        from app.providers.demo import create_demo_provider

        with patch("app.providers.demo.settings") as mock_settings:
            mock_settings.enable_demo_provider = True
            provider = create_demo_provider("materials")
            assert provider.provider_name == "demo_materials"

    def test_create_unknown_raises(self):
        from app.providers.demo import create_demo_provider

        with patch("app.providers.demo.settings") as mock_settings:
            mock_settings.enable_demo_provider = True
            with pytest.raises(ValueError, match="Unknown demo provider type"):
                create_demo_provider("nonexistent")

    def test_is_demo_provider_enabled(self):
        from app.providers.demo import is_demo_provider_enabled

        with patch("app.providers.demo.settings") as mock_settings:
            mock_settings.enable_demo_provider = True
            assert is_demo_provider_enabled() is True

            mock_settings.enable_demo_provider = False
            assert is_demo_provider_enabled() is False


# ---------------------------------------------------------------------------
# Domain Provider Wrapper tests
# ---------------------------------------------------------------------------


class TestDomainProviders:
    @pytest.mark.asyncio
    async def test_product_research_demo(self):
        from app.providers.research import ProductResearchProvider

        with patch("app.providers.research.is_demo_provider_enabled", return_value=True):
            provider = ProductResearchProvider()
            result = await provider.execute(url="https://example.com")
            assert result.success is True
            assert "product_name" in result.data

    @pytest.mark.asyncio
    async def test_material_provider_demo(self):
        from app.providers.materials import MaterialProvider

        with patch("app.providers.materials.is_demo_provider_enabled", return_value=True):
            provider = MaterialProvider()
            result = await provider.execute(query="nature")
            assert result.success is True
            assert len(result.data["materials"]) == 3

    @pytest.mark.asyncio
    async def test_digital_human_provider_demo(self):
        from app.providers.digital_human import DigitalHumanProvider

        with patch("app.providers.digital_human.is_demo_provider_enabled", return_value=True):
            provider = DigitalHumanProvider()
            result = await provider.execute()
            assert result.success is True
            assert result.data["digital_human_id"] == "demo-avatar-001"

    @pytest.mark.asyncio
    async def test_video_render_provider_demo(self):
        from app.providers.video import VideoRenderProvider

        with patch("app.providers.video.is_demo_provider_enabled", return_value=True):
            provider = VideoRenderProvider()
            result = await provider.execute(aspect_ratio="16:9", duration_seconds=30)
            assert result.success is True
            assert result.data["video_url"] == "https://example.com/demo-video.mp4"

    @pytest.mark.asyncio
    async def test_product_research_real_not_implemented(self):
        from app.providers.research import ProductResearchProvider

        with patch("app.providers.research.is_demo_provider_enabled", return_value=False):
            provider = ProductResearchProvider()
            result = await provider.execute(url="https://example.com")
            assert result.success is False
            assert result.error_code == "not_implemented"
