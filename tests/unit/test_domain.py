"""Unit tests for WP-08 Agent Film business nodes.

Covers:
  - Input normalization (product_link, files, start content)
  - Product context extraction and interaction
  - Creative strategy generation
  - Script generation (quick and deep modes)
  - Storyboard generation and interaction
  - Generation preparation and approval
  - Quick/Deep profile routing differences
"""
from __future__ import annotations

import os
import sys
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


# ---------------------------------------------------------------------------
# Input Normalization tests
# ---------------------------------------------------------------------------


class TestNormalizeStartInput:
    def test_empty_input(self):
        from app.domain.agent_film import normalize_start_input

        state = {
            "user_request": "",
            "product_link": None,
            "input_files": [],
            "language": "zh-CN",
        }
        result = normalize_start_input(state)

        assert result["user_request"] == ""
        assert result["product_link"] is None
        assert result["input_files"] == []
        assert "product_context" in result

    def test_product_link_normalization(self):
        from app.domain.agent_film import normalize_start_input

        # No protocol
        state = {
            "user_request": "test",
            "product_link": "example.com/product",
            "input_files": [],
            "language": "zh-CN",
        }
        result = normalize_start_input(state)
        assert result["product_link"] == "https://example.com/product"

        # Already has https
        state["product_link"] = "https://example.com/product"
        result = normalize_start_input(state)
        assert result["product_link"] == "https://example.com/product"

        # // prefix
        state["product_link"] = "//example.com/product"
        result = normalize_start_input(state)
        assert result["product_link"] == "https://example.com/product"

    def test_input_files_deduplication(self):
        from app.domain.agent_film import normalize_start_input

        state = {
            "user_request": "test",
            "product_link": None,
            "input_files": [
                {"url": "https://example.com/img1.jpg", "name": "img1"},
                {"url": "https://example.com/img1.jpg", "name": "img1-dup"},
                {"url": "https://example.com/img2.jpg", "name": "img2"},
            ],
            "language": "zh-CN",
        }
        result = normalize_start_input(state)
        assert len(result["input_files"]) == 2

    def test_start_content_is_json(self):
        from app.domain.agent_film import normalize_start_input
        import json

        state = {
            "user_request": "generate a video",
            "product_link": "https://example.com/product",
            "input_files": [{"url": "https://example.com/img.jpg", "name": "img"}],
            "language": "zh-CN",
        }
        result = normalize_start_input(state)
        content = result["product_context"]["raw_content"]
        parsed = json.loads(content)
        assert parsed["content"] == "generate a video"
        assert parsed["link"] == "https://example.com/product"
        assert len(parsed["material_assets"]) == 1  # .jpg → material_assets

    def test_language_normalization(self):
        from app.domain.agent_film import normalize_start_input

        state = {
            "user_request": "test",
            "product_link": None,
            "input_files": [],
            "language": "zh-CN",
        }
        result = normalize_start_input(state)
        content = result["product_context"]["raw_content"]
        assert "zh-CN" in content

        state["language"] = "en-US"
        result = normalize_start_input(state)
        content = result["product_context"]["raw_content"]
        assert "en-US" in content


# ---------------------------------------------------------------------------
# Product Context tests
# ---------------------------------------------------------------------------


class TestExtractProductContext:
    @pytest.mark.asyncio
    async def test_extract_from_link(self):
        from app.domain.agent_film import extract_product_context

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.data = {
            "product_name": "Test Product",
            "product_description": "A test product",
            "target_audience": "Adults",
            "key_selling_points": ["Quality", "Price"],
            "images": [],
        }

        with patch("app.domain.agent_film.ProductResearchProvider") as MockProvider:
            MockProvider.return_value.execute = AsyncMock(return_value=mock_result)
            state = {
                "product_link": "https://example.com/product",
                "input_files": [],
                "profile_id": "one-click-cocreate",
            }
            result = await extract_product_context(state)

        assert result["product_context"]["product_name"] == "Test Product"
        assert result["product_context"]["source"] == "link_extraction"

    @pytest.mark.asyncio
    async def test_quick_mode_fills_defaults(self):
        from app.domain.agent_film import extract_product_context

        with patch("app.domain.agent_film.ProductResearchProvider") as MockProvider:
            MockProvider.return_value.execute = AsyncMock(return_value=MagicMock(success=False))
            state = {
                "product_link": None,
                "input_files": [],
                "profile_id": "one-click-quick",
                "user_request": "generate video",
            }
            result = await extract_product_context(state)

        assert result["product_context"]["product_name"] == "未命名商品"
        assert result["product_context"]["source"] == "quick_defaults"

    @pytest.mark.asyncio
    async def test_skips_complete_context(self):
        from app.domain.agent_film import extract_product_context

        state = {
            "product_link": "https://example.com/product",
            "product_context": {
                "product_name": "Existing Product",
                "product_description": "Already complete",
            },
            "profile_id": "one-click-cocreate",
        }
        result = await extract_product_context(state)
        # Should not call provider since context is complete
        assert result["product_context"]["product_name"] == "Existing Product"


class TestBuildProductContextInteraction:
    def test_basic_interaction(self):
        from app.domain.agent_film import build_product_context_interaction

        state = {
            "profile_id": "one-click-cocreate",
            "product_context": {
                "product_name": "Test Product",
                "product_description": "A test product",
                "selling_points": ["Quality", "Price"],
                "target_audience": "Adults",
                "images": ["https://example.com/img.jpg"],
            },
        }
        result = build_product_context_interaction(state)

        assert result["intent"] == "confirm_extracted_product_context"
        assert result["render_type"] == "form"
        assert len(result["form_data"]) > 0
        assert result["actions"] == ["approve", "modify"]
        assert result["product_images"] == ["https://example.com/img.jpg"]

    def test_form_fields(self):
        from app.domain.agent_film import build_product_context_interaction

        state = {
            "profile_id": "one-click-cocreate",
            "product_context": {"product_name": "Test"},
        }
        result = build_product_context_interaction(state)

        keys = [f["key"] for f in result["form_data"]]
        assert "product_name" in keys
        assert "product_description" in keys
        assert "selling_points" in keys
        assert "aspect_ratio" in keys
        assert "video_length" in keys


# ---------------------------------------------------------------------------
# Creative Strategy tests
# ---------------------------------------------------------------------------


class TestGenerateCreativeStrategy:
    @pytest.mark.asyncio
    async def test_promotional_angle(self):
        from app.domain.agent_film import generate_creative_strategy

        state = {
            "product_context": {"product_name": "Test", "selling_points": ["Fast", "Cheap"]},
            "user_request": "促销活动视频",
            "profile_id": "one-click-quick",
        }
        result = await generate_creative_strategy(state)

        assert result["creative_strategy"]["marketing_angle"] == "promotional"
        assert result["creative_strategy"]["tone"] == "concise"

    @pytest.mark.asyncio
    async def test_deep_mode_tone(self):
        from app.domain.agent_film import generate_creative_strategy

        state = {
            "product_context": {"product_name": "Test"},
            "user_request": "品牌故事",
            "profile_id": "one-click-cocreate",
        }
        result = await generate_creative_strategy(state)

        assert result["creative_strategy"]["tone"] == "detailed"

    @pytest.mark.asyncio
    async def test_key_messages_from_selling_points(self):
        from app.domain.agent_film import generate_creative_strategy

        state = {
            "product_context": {"selling_points": ["P1", "P2", "P3", "P4"]},
            "user_request": "test",
            "profile_id": "one-click-quick",
        }
        result = await generate_creative_strategy(state)

        assert len(result["creative_strategy"]["key_messages"]) == 3


# ---------------------------------------------------------------------------
# Script Generation tests
# ---------------------------------------------------------------------------


class TestGenerateScript:
    @pytest.mark.asyncio
    async def test_quick_mode_fewer_segments(self):
        from app.domain.agent_film import generate_script

        state = {
            "product_context": {"product_name": "Test Product"},
            "creative_strategy": {"marketing_angle": "general", "key_messages": ["M1"]},
            "profile_id": "one-click-quick",
            "language": "zh-CN",
        }
        result = await generate_script(state)

        script = result["script"]
        assert len(script["segments"]) == 3  # Quick: 3 segments
        assert script["style"] == "balanced"
        assert script["total_duration"] == 30

    @pytest.mark.asyncio
    async def test_deep_mode_more_segments(self):
        from app.domain.agent_film import generate_script

        state = {
            "product_context": {"product_name": "Test Product"},
            "creative_strategy": {"marketing_angle": "brand_story", "key_messages": ["M1", "M2", "M3"]},
            "profile_id": "one-click-cocreate",
            "language": "zh-CN",
        }
        result = await generate_script(state)

        script = result["script"]
        assert len(script["segments"]) == 4  # Deep: 4 segments
        assert script["style"] == "emotional"

    @pytest.mark.asyncio
    async def test_script_has_required_fields(self):
        from app.domain.agent_film import generate_script

        state = {
            "product_context": {"product_name": "Test"},
            "creative_strategy": {},
            "profile_id": "one-click-quick",
        }
        result = await generate_script(state)

        script = result["script"]
        assert "title" in script
        assert "total_duration" in script
        assert "segments" in script
        assert "language" in script

        for seg in script["segments"]:
            assert "segment" in seg
            assert "time" in seg
            assert "camera_desc" in seg
            assert "script_content" in seg
            assert "core_purpose" in seg


# ---------------------------------------------------------------------------
# Storyboard tests
# ---------------------------------------------------------------------------


class TestGenerateStoryboard:
    @pytest.mark.asyncio
    async def test_storyboard_from_script(self):
        from app.domain.agent_film import generate_storyboard

        state = {
            "script": {
                "title": "Test Script",
                "style": "balanced",
                "language": "zh-CN",
                "segments": [
                    {"segment": 1, "time": "0-10s", "camera_desc": "Wide shot", "script_content": "Hello", "core_purpose": "intro", "duration_seconds": 10},
                    {"segment": 2, "time": "10-20s", "camera_desc": "Close up", "script_content": "World", "core_purpose": "detail", "duration_seconds": 10},
                ],
            },
        }
        result = await generate_storyboard(state)

        storyboard = result["storyboard"]
        assert storyboard["title"] == "Test Script"
        assert storyboard["total_shots"] == 2
        assert len(storyboard["shots"]) == 2
        assert storyboard["shots"][0]["camera_description"] == "Wide shot"
        assert storyboard["shots"][0]["voiceover"] == "Hello"


class TestBuildStoryboardInteraction:
    def test_basic_interaction(self):
        from app.domain.agent_film import build_storyboard_interaction

        state = {
            "storyboard": {
                "title": "Test Storyboard",
                "shots": [
                    {"shot_number": 1, "time_window": "0-10s", "camera_description": "Wide", "core_purpose": "intro", "voiceover": "Hello"},
                ],
            },
        }
        result = build_storyboard_interaction(state)

        assert result["intent"] == "review_storyboard_script"
        assert result["render_type"] == "table_review"
        assert len(result["table_data"]["rows"]) == 1
        assert result["actions"] == ["approve", "modify", "deny", "regenerate"]

    def test_table_columns(self):
        from app.domain.agent_film import build_storyboard_interaction

        state = {"storyboard": {"shots": []}}
        result = build_storyboard_interaction(state)

        columns = result["table_data"]["columns"]
        assert "shot" in columns
        assert "time" in columns
        assert "camera_desc" in columns
        assert "core_purpose" in columns


# ---------------------------------------------------------------------------
# Generation Preparation tests
# ---------------------------------------------------------------------------


class TestPrepareGeneration:
    @pytest.mark.asyncio
    async def test_prepare_returns_materials_and_render_job(self):
        from app.domain.agent_film import prepare_generation

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.data = {"materials": [{"id": "m1", "name": "Material 1"}]}

        state = {
            "profile_id": "one-click-cocreate",
            "product_context": {"product_name": "Test"},
            "script": {"total_duration": 30, "style": "balanced"},
            "storyboard": {"total_shots": 4},
            "digital_human": None,
        }

        with patch("app.domain.agent_film.MaterialProvider") as MockProvider:
            MockProvider.return_value.execute = AsyncMock(return_value=mock_result)
            result = await prepare_generation(state)

        assert "materials" in result
        assert "render_job" in result
        assert result["render_job"]["duration_seconds"] == 30
        assert result["render_job"]["total_points"] > 0


class TestBuildGenerationApproval:
    def test_basic_approval(self):
        from app.domain.agent_film import build_generation_approval

        state = {
            "profile_id": "one-click-cocreate",
            "product_context": {"product_name": "Test Product"},
            "script": {"total_duration": 30},
            "storyboard": {"total_shots": 4},
            "render_job": {
                "duration_seconds": 30,
                "billing_seconds": 30,
                "video_points": 1200,
                "digital_human_points": 0,
                "total_points": 1200,
            },
            "digital_human": None,
        }
        result = build_generation_approval(state)

        assert result["intent"] == "confirm_generation_start"
        assert result["render_type"] == "generation_cost_confirm"
        assert result["cost_breakdown"]["total_points"] == 1200
        assert result["auto_approve_countdown_seconds"] == 10
        assert result["actions"] == ["approve", "cancel"]
        assert result["product_name"] == "Test Product"
        assert result["shot_count"] == 4


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------


class TestHelpers:
    def test_normalize_product_link_adds_https(self):
        from app.domain.agent_film import _normalize_product_link

        assert _normalize_product_link("example.com") == "https://example.com"
        assert _normalize_product_link("http://example.com") == "http://example.com"
        assert _normalize_product_link("https://example.com") == "https://example.com"
        assert _normalize_product_link("//example.com") == "https://example.com"
        assert _normalize_product_link("") is None
        assert _normalize_product_link(None) is None

    def test_normalize_language(self):
        from app.domain.agent_film import _normalize_language

        assert _normalize_language("zh-CN") == "zh-CN"
        assert _normalize_language("zh-cn") == "zh-CN"
        assert _normalize_language("en-US") == "en-US"
        assert _normalize_language("en-us") == "en-US"

    def test_round_to_billing_increment(self):
        from app.domain.agent_film import _round_to_billing_increment

        assert _round_to_billing_increment(10) == 10
        assert _round_to_billing_increment(12) == 15
        assert _round_to_billing_increment(17) == 20
        assert _round_to_billing_increment(0) == 5

    def test_determine_marketing_angle(self):
        from app.domain.agent_film import _determine_marketing_angle

        assert _determine_marketing_angle("促销活动", []) == "promotional"
        assert _determine_marketing_angle("新品上市", []) == "new_launch"
        assert _determine_marketing_angle("品牌故事", []) == "brand_story"
        assert _determine_marketing_angle("test", ["Quality"]) == "feature_focused"
        assert _determine_marketing_angle("test", []) == "general"

    def test_parse_duration(self):
        from app.domain.agent_film import _parse_duration

        assert _parse_duration("30s") == 30
        assert _parse_duration("60s") == 60
        assert _parse_duration("invalid") == 30
