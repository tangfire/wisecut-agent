"""Unit tests for WP-06 LangGraph Runtime."""

from __future__ import annotations

import os
import sys

import pytest
from langchain_openai import ChatOpenAI

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


# ---------------------------------------------------------------------------
# AgentFilmState tests
# ---------------------------------------------------------------------------


class TestAgentFilmState:
    def test_create_initial_state_defaults(self):
        from app.graph.state import create_initial_state

        state = create_initial_state(
            conversation_id="conv-1",
            run_id="run-1",
        )
        assert state["conversation_id"] == "conv-1"
        assert state["run_id"] == "run-1"
        assert state["profile_id"] == "one-click-quick"
        assert state["language"] == "zh-CN"
        assert state["user_request"] == ""
        assert state["product_link"] is None
        assert state["input_files"] == []
        assert state["product_context"] == {}
        assert state["creative_strategy"] == {}
        assert state["script"] == {}
        assert state["storyboard"] == {}
        assert state["materials"] == []
        assert state["digital_human"] is None
        assert state["render_job"] is None
        assert state["artifacts"] == []
        assert state["pending_interaction"] is None
        assert state["pending_approval"] is None
        assert state["errors"] == []
        assert state["retry_count"] == 0

    def test_create_initial_state_with_values(self):
        from app.graph.state import create_initial_state

        state = create_initial_state(
            conversation_id="conv-1",
            run_id="run-1",
            profile_id="one-click-cocreate",
            language="en-US",
            user_request="Generate a video",
            product_link="https://example.com/product",
        )
        assert state["profile_id"] == "one-click-cocreate"
        assert state["language"] == "en-US"
        assert state["user_request"] == "Generate a video"
        assert state["product_link"] == "https://example.com/product"


# ---------------------------------------------------------------------------
# Profile tests
# ---------------------------------------------------------------------------


class TestProfiles:
    def test_quick_profile_defaults(self):
        from app.graph.profiles import QUICK_PROFILE

        assert QUICK_PROFILE.profile_id == "one-click-quick"
        assert QUICK_PROFILE.mode == "quick"
        assert QUICK_PROFILE.confirm_product_context is False
        assert QUICK_PROFILE.confirm_script_or_storyboard is False

    def test_deep_profile_defaults(self):
        from app.graph.profiles import DEEP_PROFILE

        assert DEEP_PROFILE.profile_id == "one-click-cocreate"
        assert DEEP_PROFILE.mode == "deep"
        assert DEEP_PROFILE.confirm_product_context is True
        assert DEEP_PROFILE.confirm_script_or_storyboard is True

    def test_get_profile_unknown_falls_back_to_quick(self):
        from app.graph.profiles import get_profile

        profile = get_profile("nonexistent-profile")
        assert profile.profile_id == "one-click-quick"

    def test_profile_id_to_mode(self):
        from app.graph.profiles import profile_id_to_mode

        assert profile_id_to_mode("one-click-quick") == "quick"
        assert profile_id_to_mode("one-click-cocreate") == "deep"
        assert profile_id_to_mode("unknown") == "quick"


# ---------------------------------------------------------------------------
# Routing tests
# ---------------------------------------------------------------------------


class TestRouting:
    def test_needs_product_confirmation_quick_skips(self):
        from app.graph.routing import needs_product_confirmation

        state = {
            "profile_id": "one-click-quick",
            "product_context": {},
            "pending_interaction": None,
        }
        assert needs_product_confirmation(state) == "continue"

    def test_needs_product_confirmation_deep_with_empty_context(self):
        from app.graph.routing import needs_product_confirmation

        state = {
            "profile_id": "one-click-cocreate",
            "product_context": {},
            "pending_interaction": None,
        }
        assert needs_product_confirmation(state) == "request_review"

    def test_needs_product_confirmation_deep_with_complete_context(self):
        from app.graph.routing import needs_product_confirmation

        state = {
            "profile_id": "one-click-cocreate",
            "product_context": {
                "product_name": "Test Product",
                "product_description": "A test product",
                "target_audience": "Adults",
            },
            "pending_interaction": None,
        }
        assert needs_product_confirmation(state) == "continue"

    def test_review_script_or_storyboard_quick_skips(self):
        from app.graph.routing import review_script_or_storyboard

        state = {
            "profile_id": "one-click-quick",
            "script": {},
            "storyboard": {},
            "pending_interaction": None,
        }
        assert review_script_or_storyboard(state) == "continue"

    def test_review_script_or_storyboard_deep_with_script(self):
        from app.graph.routing import review_script_or_storyboard

        state = {
            "profile_id": "one-click-cocreate",
            "script": {"content": "script content"},
            "storyboard": {},
            "pending_interaction": None,
        }
        assert review_script_or_storyboard(state) == "continue"

    def test_is_terminal_with_cancel(self):
        from app.graph.routing import is_terminal

        state = {
            "pending_interaction": {"action": "cancel"},
            "errors": [],
            "retry_count": 0,
        }
        assert is_terminal(state) == "terminal"

    def test_is_terminal_with_too_many_errors(self):
        from app.graph.routing import is_terminal

        state = {
            "pending_interaction": None,
            "errors": [],
            "retry_count": 6,
        }
        assert is_terminal(state) == "terminal"

    def test_is_terminal_continue(self):
        from app.graph.routing import is_terminal

        state = {
            "pending_interaction": None,
            "errors": [],
            "retry_count": 0,
        }
        assert is_terminal(state) == "continue"

    def test_should_retry_within_limit(self):
        from app.graph.routing import should_retry

        state = {"retry_count": 0, "profile_id": "one-click-quick"}
        assert should_retry(state) == "retry"

    def test_should_retry_exceeds_limit(self):
        from app.graph.routing import should_retry

        state = {"retry_count": 2, "profile_id": "one-click-quick"}
        assert should_retry(state) == "terminal"


# ---------------------------------------------------------------------------
# LLM Factory tests
# ---------------------------------------------------------------------------


class TestLLMFactory:
    def test_create_demo_llm(self):
        from app.llm.factory import create_llm

        llm = create_llm(provider="demo")
        assert llm._llm_type == "demo"

    def test_create_openai_compatible_llm(self):
        from app.llm.factory import create_llm

        llm = create_llm(
            provider="openai-compatible",
            base_url="http://localhost:8000/v1",
            api_key="test-key",
        )
        assert isinstance(llm, ChatOpenAI)

    def test_create_unknown_provider_raises(self):
        from app.llm.factory import create_llm

        with pytest.raises(ValueError, match="Unknown LLM provider"):
            create_llm(provider="unknown")


# ---------------------------------------------------------------------------
# Prompt Profile tests
# ---------------------------------------------------------------------------


class TestPromptProfiles:
    def test_get_prompt_profile(self):
        from app.llm.profiles import get_prompt_profile

        profile = get_prompt_profile("collect_product_context")
        assert profile.prompt_name == "collect_product_context"
        assert profile.prompt_version == "1.0.0"

    def test_get_unknown_prompt_falls_back(self):
        from app.llm.profiles import get_prompt_profile

        profile = get_prompt_profile("nonexistent")
        assert profile.prompt_name == "collect_product_context"


# ---------------------------------------------------------------------------
# Graph Builder tests
# ---------------------------------------------------------------------------


class TestGraphBuilder:
    def test_build_default_graph(self):
        from app.graph.builder import build_default_graph

        graph = build_default_graph()
        assert graph is not None

    def test_graph_has_expected_nodes(self):
        from app.graph.builder import AgentFilmGraphBuilder, normalize_input

        builder = AgentFilmGraphBuilder()
        builder.add_node("normalize_input", normalize_input)
        builder.add_edge("normalize_input", "collect_product_context")
        g = builder.build()
        assert g is not None
