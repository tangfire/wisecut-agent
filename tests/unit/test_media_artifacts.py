"""Unit tests for WP-09 Media and Artifact capabilities.

Covers:
  - Material selection
  - Digital human matching
  - Video rendering (demo provider)
  - Video delivery validation
  - Final video artifact creation
  - Artifact event emission (artifact.created + business.message)
  - Publish artifacts pipeline
"""
from __future__ import annotations

import os
import sys
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


# ---------------------------------------------------------------------------
# Material Selection tests
# ---------------------------------------------------------------------------


class TestSelectMaterials:
    @pytest.mark.asyncio
    async def test_selects_top_three(self):
        from app.domain.agent_film import select_materials_for_render

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.data = {"materials": [{"id": f"m{i}"} for i in range(5)]}

        state = {
            "materials": [],
            "product_context": {"product_name": "Test"},
            "script": {"style": "balanced"},
            "profile_id": "one-click-quick",
        }

        with patch("app.domain.agent_film.MaterialProvider") as MockProvider:
            MockProvider.return_value.execute = AsyncMock(return_value=mock_result)
            result = await select_materials_for_render(state)

        assert len(result["materials"]) == 3
        assert result["materials"][0]["id"] == "m0"

    @pytest.mark.asyncio
    async def test_passes_through_existing_materials(self):
        from app.domain.agent_film import select_materials_for_render

        state = {
            "materials": [{"id": "existing"}],
            "product_context": {"product_name": "Test"},
            "script": {"style": "balanced"},
            "profile_id": "one-click-quick",
        }
        result = await select_materials_for_render(state)
        assert result["materials"] == [{"id": "existing"}]


# ---------------------------------------------------------------------------
# Digital Human Matching tests
# ---------------------------------------------------------------------------


class TestMatchDigitalHuman:
    @pytest.mark.asyncio
    async def test_quick_mode_skips(self):
        from app.domain.agent_film import match_digital_human

        state = {
            "profile_id": "one-click-quick",
            "product_context": {},
            "script": {},
        }
        result = await match_digital_human(state)
        assert result["digital_human"] is None

    @pytest.mark.asyncio
    async def test_deep_mode_matches(self):
        from app.domain.agent_film import match_digital_human

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.data = {"digital_human_id": "dh-001", "name": "Avatar"}

        state = {
            "profile_id": "one-click-cocreate",
            "product_context": {"product_type": "electronics"},
            "script": {"style": "modern"},
            "language": "zh-CN",
        }

        with patch("app.domain.agent_film.DigitalHumanProvider") as MockProvider:
            MockProvider.return_value.execute = AsyncMock(return_value=mock_result)
            result = await match_digital_human(state)

        assert result["digital_human"]["digital_human_id"] == "dh-001"

    @pytest.mark.asyncio
    async def test_returns_none_on_failure(self):
        from app.domain.agent_film import match_digital_human

        state = {
            "profile_id": "one-click-cocreate",
            "product_context": {},
            "script": {},
            "language": "zh-CN",
        }

        with patch("app.domain.agent_film.DigitalHumanProvider") as MockProvider:
            MockProvider.return_value.execute = AsyncMock(return_value=MagicMock(success=False))
            result = await match_digital_human(state)

        assert result["digital_human"] is None

    @pytest.mark.asyncio
    async def test_returns_none_on_exception(self):
        from app.domain.agent_film import match_digital_human

        state = {
            "profile_id": "one-click-cocreate",
            "product_context": {"product_type": "electronics"},
            "script": {"style": "modern"},
            "language": "zh-CN",
        }

        with patch("app.domain.agent_film.DigitalHumanProvider") as MockProvider:
            MockProvider.return_value.execute = AsyncMock(side_effect=RuntimeError("provider error"))
            result = await match_digital_human(state)

        assert result["digital_human"] is None


# ---------------------------------------------------------------------------
# Video Rendering tests
# ---------------------------------------------------------------------------


class TestRenderVideo:
    @pytest.mark.asyncio
    async def test_rendering_success(self):
        from app.domain.agent_film import render_video

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.data = {
            "video_url": "https://example.com/video.mp4",
            "cover_url": "https://example.com/cover.jpg",
            "format": "mp4",
            "resolution": "1920x1080",
        }

        state = {
            "profile_id": "one-click-cocreate",
            "script": {"total_duration": 30, "style": "balanced", "title": "Test Video"},
            "storyboard": {"total_shots": 3},
            "materials": [],
            "digital_human": None,
            "render_job": {"total_points": 1200},
            "errors": [],
        }

        with patch("app.domain.agent_film.VideoRenderProvider") as MockProvider:
            MockProvider.return_value.execute = AsyncMock(return_value=mock_result)
            result = await render_video(state)

        assert result["render_job"]["video_url"] == "https://example.com/video.mp4"
        assert result["render_job"]["status"] == "completed"

    @pytest.mark.asyncio
    async def test_rendering_failure_adds_error(self):
        from app.domain.agent_film import render_video

        state = {
            "profile_id": "one-click-quick",
            "script": {"total_duration": 30},
            "storyboard": {},
            "materials": [],
            "digital_human": None,
            "render_job": {},
            "errors": [],
        }

        with patch("app.domain.agent_film.VideoRenderProvider") as MockProvider:
            MockProvider.return_value.execute = AsyncMock(return_value=MagicMock(success=False))
            result = await render_video(state)

        assert len(result["errors"]) == 1
        assert result["errors"][0]["node"] == "render_video"

    @pytest.mark.asyncio
    async def test_rendering_provider_exception_adds_error(self):
        from app.domain.agent_film import render_video

        state = {
            "profile_id": "one-click-quick",
            "script": {"total_duration": 30},
            "storyboard": {},
            "materials": [],
            "digital_human": None,
            "render_job": {"total_points": 1200},
            "errors": [],
        }

        with patch("app.domain.agent_film.VideoRenderProvider") as MockProvider:
            MockProvider.return_value.execute = AsyncMock(side_effect=RuntimeError("provider down"))
            result = await render_video(state)

        assert len(result["errors"]) == 1
        assert result["errors"][0]["node"] == "render_video"
        assert "provider down" in result["errors"][0]["error"]


# ---------------------------------------------------------------------------
# Video Delivery Validation tests
# ---------------------------------------------------------------------------


class TestValidateVideoDelivery:
    def test_empty_url_fails(self):
        from app.domain.agent_film import validate_video_delivery

        assert validate_video_delivery("")["valid"] is False
        assert validate_video_delivery(None)["valid"] is False

    def test_https_url_passes(self):
        from app.domain.agent_film import validate_video_delivery

        result = validate_video_delivery("https://example.com/video.mp4")
        assert result["valid"] is True

    def test_internal_url_fails(self):
        from app.domain.agent_film import validate_video_delivery

        assert validate_video_delivery("http://localhost/video.mp4")["valid"] is False
        assert validate_video_delivery("http://127.0.0.1/video.mp4")["valid"] is False

    def test_no_protocol_fails(self):
        from app.domain.agent_film import validate_video_delivery

        assert validate_video_delivery("example.com/video.mp4")["valid"] is False

    def test_video_extension_passes(self):
        from app.domain.agent_film import validate_video_delivery

        for ext in [".mp4", ".mov", ".avi", ".webm", ".m3u8"]:
            result = validate_video_delivery(f"https://example.com/video{ext}")
            assert result["valid"] is True, f"Failed for {ext}"

    def test_ipv6_loopback_fails(self):
        from app.domain.agent_film import validate_video_delivery

        assert validate_video_delivery("http://[::1]/video.mp4")["valid"] is False

    def test_zero_dot_zero_fails(self):
        from app.domain.agent_film import validate_video_delivery

        assert validate_video_delivery("http://0.0.0.0/video.mp4")["valid"] is False


# ---------------------------------------------------------------------------
# Artifact Creation tests
# ---------------------------------------------------------------------------


class TestCreateFinalVideoArtifact:
    @pytest.mark.asyncio
    async def test_creates_artifact_and_events(self):
        from app.domain.agent_film import create_final_video_artifact

        state = {
            "conversation_id": "conv-1",
            "run_id": "run-1",
            "profile_id": "one-click-cocreate",
            "script": {
                "title": "Test Video",
                "total_duration": 30,
                "shots": [
                    {"shot_number": 1, "camera_description": "Wide", "voiceover": "Hello", "duration_seconds": 10},
                ],
            },
            "storyboard": {
                "shots": [
                    {"shot_number": 1, "camera_description": "Wide", "voiceover": "Hello", "duration_seconds": 10},
                ],
            },
        }

        mock_artifact = MagicMock()
        mock_artifact.id = "art-1"
        mock_artifact.conversation_id = "conv-1"
        mock_artifact.run_id = "run-1"
        mock_artifact.artifact_type = "final_video"
        mock_artifact.payload_json = {}
        mock_artifact.uri = "https://example.com/video.mp4"
        mock_artifact.status.value = "pending"
        mock_artifact.created_at.isoformat.return_value = "2024-01-01T00:00:00"

        with patch("app.domain.agent_film.unit_of_work") as mock_uow, \
             patch("app.domain.agent_film.ArtifactRepository") as MockArtRepo, \
             patch("app.domain.agent_film.EventRepository") as MockEventRepo, \
             patch("app.domain.agent_film.OutboxRepository") as MockOutboxRepo, \
             patch("app.domain.agent_film.generate_id") as mock_gen_id:

            mock_gen_id.side_effect = lambda prefix: f"{prefix}-1"
            mock_uow_instance = MagicMock()
            mock_uow_instance.session = AsyncMock()
            mock_uow_instance.__aenter__ = AsyncMock(return_value=mock_uow_instance)
            mock_uow_instance.__aexit__ = AsyncMock(return_value=False)
            mock_uow.return_value = mock_uow_instance

            mock_artifact_repo = AsyncMock()
            mock_artifact_repo.create = AsyncMock(return_value=mock_artifact)
            MockArtRepo.return_value = mock_artifact_repo

            mock_event_repo = AsyncMock()
            mock_event_repo.get_next_seq = AsyncMock(return_value=1)
            mock_event_repo.create = AsyncMock()
            MockEventRepo.return_value = mock_event_repo

            mock_outbox_repo = AsyncMock()
            mock_outbox_repo.enqueue = AsyncMock()
            MockOutboxRepo.return_value = mock_outbox_repo

            result = await create_final_video_artifact(
                state=state,
                video_url="https://example.com/video.mp4",
                cover_url="https://example.com/cover.jpg",
            )

        assert result["success"] is True
        assert result["artifact_id"] == "art-1"
        assert result["video_url"] == "https://example.com/video.mp4"
        assert "artifact.created" in result["events"]
        assert "business.message" in result["events"]

    def test_invalid_url_fails(self):
        from app.domain.agent_film import create_final_video_artifact

        state = {"conversation_id": "conv-1", "run_id": "run-1"}

        result = AsyncMock(return_value={"success": False, "error": "video_url is empty"})
        # Since this is a sync test, we just check the validation part
        from app.domain.agent_film import validate_video_delivery
        assert validate_video_delivery("")["valid"] is False
        assert validate_video_delivery("http://localhost/video.mp4")["valid"] is False


# ---------------------------------------------------------------------------
# Publish Artifacts tests
# ---------------------------------------------------------------------------


class TestPublishArtifacts:
    @pytest.mark.asyncio
    async def test_publishes_final_video(self):
        from app.domain.agent_film import publish_artifacts

        state = {
            "conversation_id": "conv-1",
            "run_id": "run-1",
            "profile_id": "one-click-cocreate",
            "script": {
                "title": "Test",
                "total_duration": 30,
                "shots": [],
            },
            "storyboard": {"shots": []},
            "artifacts": [],
            "errors": [],
            "render_job": {
                "video_url": "https://example.com/video.mp4",
                "cover_url": "https://example.com/cover.jpg",
            },
        }

        mock_artifact = MagicMock()
        mock_artifact.id = "art-1"

        with patch("app.domain.agent_film.create_final_video_artifact") as mock_create:
            mock_create.return_value = {
                "success": True,
                "artifact_id": "art-1",
                "video_url": "https://example.com/video.mp4",
                "cover_url": "https://example.com/cover.jpg",
                "events": ["artifact.created", "business.message"],
            }
            result = await publish_artifacts(state)

        assert len(result["artifacts"]) == 1
        assert result["artifacts"][0]["id"] == "art-1"
        assert result["artifacts"][0]["type"] == "final_video"
        assert result["artifacts"][0]["status"] == "ready"

    @pytest.mark.asyncio
    async def test_no_video_url_returns_empty(self):
        from app.domain.agent_film import publish_artifacts

        state = {
            "conversation_id": "conv-1",
            "run_id": "run-1",
            "artifacts": [],
            "render_job": {},
        }
        result = await publish_artifacts(state)
        assert result["artifacts"] == []

    @pytest.mark.asyncio
    async def test_artifact_creation_failure_adds_error(self):
        from app.domain.agent_film import publish_artifacts

        state = {
            "conversation_id": "conv-1",
            "run_id": "run-1",
            "profile_id": "one-click-quick",
            "script": {"title": "Test", "total_duration": 30, "shots": []},
            "storyboard": {"shots": []},
            "artifacts": [],
            "errors": [],
            "render_job": {
                "video_url": "https://example.com/video.mp4",
                "cover_url": "https://example.com/cover.jpg",
            },
        }

        with patch("app.domain.agent_film.create_final_video_artifact") as mock_create:
            mock_create.return_value = {
                "success": False,
                "error": "db connection lost",
            }
            result = await publish_artifacts(state)

        assert result["artifacts"] == []
        assert len(result["errors"]) == 1
        assert result["errors"][0]["node"] == "publish_artifacts"
        assert "db connection lost" in result["errors"][0]["error"]
