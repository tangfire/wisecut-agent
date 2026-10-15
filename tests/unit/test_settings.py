"""Unit tests for app configuration and protocol helpers."""

from __future__ import annotations

import os
import sys

import pytest

# Ensure app package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


class TestSettings:
    def test_defaults(self):
        from app.settings import Environment, Settings

        s = Settings(debug=False)
        assert s.app_env == Environment.LOCAL_DEMO
        assert s.port == 10728
        assert s.service_name == "wisecut-agent"

    def test_production_requires_real_providers(self):
        from app.settings import Environment, Settings

        with pytest.raises(Exception):
            Settings(app_env=Environment.PRODUCTION, enable_demo_provider=True)

        with pytest.raises(Exception):
            Settings(app_env=Environment.PRODUCTION, llm_provider="demo")

    def test_demo_env_allows_demo_providers(self):
        from app.settings import Environment, Settings

        s = Settings(app_env=Environment.LOCAL_DEMO, enable_demo_provider=True)
        assert s.is_demo_env is True

    def test_cors_origins_parsing(self):
        from app.settings import Settings

        s = Settings(allowed_origins="http://a.com, http://b.com , http://c.com")
        assert s.cors_origins_list == ["http://a.com", "http://b.com", "http://c.com"]

    def test_database_url_sync_replaces_driver(self):
        from app.settings import Settings

        s = Settings(database_url="postgresql+asyncpg://user:pass@host/db")
        assert s.database_url_sync == "postgresql://user:pass@host/db"

    def test_environment_normalization(self):
        from app.settings import Environment, Settings

        assert Settings(app_env="LOCAL_DEMO").app_env == Environment.LOCAL_DEMO
        assert Settings(app_env="local-llm").app_env == Environment.LOCAL_LLM
        assert Settings(app_env="staging").app_env == Environment.STAGING
        assert Settings(
            app_env="production",
            enable_demo_provider=False,
            llm_provider="openai-compatible",
        ).app_env == Environment.PRODUCTION

    def test_unknown_environment_raises(self):
        from app.settings import Settings

        with pytest.raises(Exception):
            Settings(app_env="unknown-env")


class TestProtocolHelpers:
    def test_terminal_event_detection(self):
        from app.protocol.sse import is_terminal_event

        assert is_terminal_event("run.completed") is True
        assert is_terminal_event("run.failed") is True
        assert is_terminal_event("run.cancelled") is True
        assert is_terminal_event("tool.started") is False
        assert is_terminal_event("interaction.requested") is False

    def test_clamp_after_seq(self):
        from app.protocol.sse import clamp_after_seq

        assert clamp_after_seq(-1) == 0
        assert clamp_after_seq(0) == 0
        assert clamp_after_seq(5) == 5

    def test_language_normalization(self):
        from app.protocol.language import normalize_response_language

        assert normalize_response_language("zh-CN") == "zh-CN"
        assert normalize_response_language("zh") == "zh-CN"
        assert normalize_response_language("en-US") == "en-US"
        assert normalize_response_language("en") == "en-US"
        assert normalize_response_language("") == "zh-CN"

    def test_sse_roundtrip(self):
        import json

        from app.protocol.sse import decode_sse_events, encode_sse_event

        data = {"seq": 1, "payload": {"tool_name": "test"}}
        encoded = encode_sse_event("evt-1", "tool.started", data)
        decoded = decode_sse_events(encoded)
        assert len(decoded) == 1
        assert decoded[0]["event"] == "tool.started"
        assert json.loads(decoded[0]["data"])["seq"] == 1
