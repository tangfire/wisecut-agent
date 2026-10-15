"""Integration tests for MAA API endpoints (WP-04)."""

from __future__ import annotations

import os
import sys

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

# ---------------------------------------------------------------------------
# Database and app setup
# ---------------------------------------------------------------------------

from app.persistence.models import Base  # noqa: E402


@pytest_asyncio.fixture
async def app():
    """Create test FastAPI app with in-memory SQLite and fresh schema."""
    from app.main import create_app
    from app.settings import Settings

    settings = Settings(
        app_env="local-demo",
        debug=False,
        allowed_origins="*",
        service_name="wisecut-agent",
        version="0.1.0",
        port=10728,
        log_level="info",
        log_format="text",
        database_url="sqlite+aiosqlite:///:memory:",
        redis_url="redis://localhost:6379/0",
        rabbitmq_url="amqp://guest:guest@localhost:5672/",
        enable_demo_provider=True,
        llm_provider="demo",
    )

    # Directly override the engine module's settings reference so that
    # get_engine() / get_session_factory() use the test database URL
    # for the entire lifetime of the test (not just during create_app).
    import app.persistence.engine as engine_module
    from app.settings import settings as original_settings

    engine_module.settings = settings
    engine_module._async_session_factory = None
    engine_module._engine = None

    app = create_app(settings=settings)

    # Create tables on the app's engine
    engine = engine_module.get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield app

    # Teardown: drop tables and dispose engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
    engine_module._async_session_factory = None
    engine_module._engine = None
    engine_module.settings = original_settings


@pytest_asyncio.fixture
async def client(app):
    """Async test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


# ---------------------------------------------------------------------------
# Health endpoint tests
# ---------------------------------------------------------------------------


class TestHealthEndpoints:
    async def test_health_returns_ok(self, client: AsyncClient):
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    async def test_version_returns_service_info(self, client: AsyncClient):
        response = await client.get("/version")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "wisecut-agent"
        assert "version" in data
        assert "env" in data


# ---------------------------------------------------------------------------
# Conversation endpoint tests
# ---------------------------------------------------------------------------


class TestConversationAPI:
    async def test_create_conversation(self, client: AsyncClient):
        response = await client.post(
            "/conversations",
            json={
                "title": "测试会话",
                "agent_profile_id": "one-click-quick",
                "metadata": {"user_id": "1001", "project_id": "2001"},
            },
            headers={"X-User-ID": "1001", "X-Project-ID": "2001"},
        )
        assert response.status_code == 201
        data = response.json()
        assert "conversation_id" in data
        assert "langgraph_thread_id" in data
        assert data["status"] == "created"

    async def test_create_conversation_validates_title_length(self, client: AsyncClient):
        response = await client.post(
            "/conversations",
            json={"title": "x" * 250},
        )
        assert response.status_code == 422  # Validation error

    async def test_get_conversation_not_found(self, client: AsyncClient):
        response = await client.get("/conversations/nonexistent-id")
        assert response.status_code == 404
        data = response.json()
        assert data["status_code"] == 404
        assert "not found" in data["body"]


# ---------------------------------------------------------------------------
# Message endpoint tests
# ---------------------------------------------------------------------------


class TestMessageAPI:
    async def test_post_message(self, client: AsyncClient):
        # First create a conversation
        conv_response = await client.post(
            "/conversations",
            json={"title": "test"},
            headers={"X-User-ID": "1001", "X-Project-ID": "2001"},
        )
        conv_id = conv_response.json()["conversation_id"]

        # Post a message
        response = await client.post(
            f"/conversations/{conv_id}/messages",
            json={"type": "message", "content": "帮我生成一个视频"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["conversation_id"] == conv_id
        assert "run_id" in data
        assert data["accepted_as_inbox"] is True
        assert "events_url" in data

    async def test_message_idempotency(self, client: AsyncClient):
        """Posting the same request_id twice should return the same result."""
        conv_response = await client.post(
            "/conversations",
            json={"title": "idempotency test"},
            headers={"X-User-ID": "1001", "X-Project-ID": "2001"},
        )
        conv_id = conv_response.json()["conversation_id"]
        request_id = "idempotent-req-001"

        body = {
            "type": "message",
            "content": "test",
            "metadata": {"request_id": request_id, "run_id": "run-1"},
        }

        response1 = await client.post(f"/conversations/{conv_id}/messages", json=body)
        response2 = await client.post(f"/conversations/{conv_id}/messages", json=body)

        assert response1.status_code == 200
        assert response2.status_code == 200
        # Should return the same run_id
        assert response1.json()["run_id"] == response2.json()["run_id"]

    async def test_list_messages(self, client: AsyncClient):
        conv_response = await client.post(
            "/conversations",
            json={"title": "list test"},
            headers={"X-User-ID": "1001", "X-Project-ID": "2001"},
        )
        conv_id = conv_response.json()["conversation_id"]

        # Post a few messages
        for i in range(3):
            await client.post(
                f"/conversations/{conv_id}/messages",
                json={"type": "message", "content": f"message {i}"},
            )

        # List messages
        response = await client.get(f"/conversations/{conv_id}/messages")
        assert response.status_code == 200
        messages = response.json()
        assert len(messages) == 3


# ---------------------------------------------------------------------------
# SSE endpoint tests
# ---------------------------------------------------------------------------


class TestSSEAPI:
    async def test_sse_endpoint_returns_event_stream(self, client: AsyncClient):
        response = await client.get(
            "/runs/test-run/events",
            params={"after_seq": "0", "live": "true"},
            headers={"Accept": "text/event-stream"},
        )
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]

    async def test_sse_with_after_seq(self, client: AsyncClient):
        """SSE endpoint accepts after_seq parameter."""
        response = await client.get(
            "/runs/test-run/events",
            params={"after_seq": "5", "live": "true"},
        )
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# Run endpoint tests
# ---------------------------------------------------------------------------


class TestRunAPI:
    async def test_cancel_run_not_found(self, client: AsyncClient):
        response = await client.post("/runs/nonexistent-run/cancel")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Approval endpoint tests
# ---------------------------------------------------------------------------


class TestApprovalAPI:
    async def test_decide_approval_not_found(self, client: AsyncClient):
        response = await client.post(
            "/approvals/nonexistent-approval/decide",
            json={"decision": {"action": "approve"}},
        )
        assert response.status_code == 404
