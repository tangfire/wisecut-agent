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
        database_url="sqlite+aiosqlite:///.test_shared.db",
        redis_url="redis://localhost:6379/0",
        rabbitmq_url="amqp://guest:guest@localhost:5672/",
        enable_demo_provider=True,
        llm_provider="demo",
    )

    # Directly override the engine module's settings reference so that
    # get_engine() / get_session_factory() use the test database URL.
    import app.persistence.engine as engine_module
    import app.persistence.sync_engine as sync_engine_module
    from app.settings import settings as original_settings

    engine_module.settings = settings
    engine_module._async_session_factory = None
    engine_module._engine = None

    # Configure sync engine for API routes (same test DB file)
    sync_engine_module.configure_sync_engine(settings)
    sync_engine_module._engine = None
    sync_engine_module._session_factory = None

    app = create_app(settings=settings)

    # Create tables on both engines (shared SQLite file)
    engine = engine_module.get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    sync_engine = sync_engine_module.get_sync_engine()
    Base.metadata.create_all(sync_engine)

    yield app

    # Teardown: drop tables and dispose engines
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
    engine_module._async_session_factory = None
    engine_module._engine = None
    engine_module.settings = original_settings

    # Reset sync engine
    sync_engine_module._engine = None
    sync_engine_module._session_factory = None

    # Clean up test DB file
    import os
    for f in [".test_shared.db", ".test_shared.db.wal", ".test_shared.db-shm"]:
        if os.path.exists(f):
            os.remove(f)


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
        """Posting messages should succeed and return valid run_ids.

        Note: Idempotency is enforced by the Worker (via request_id dedup
        in RabbitMQ), not at the API layer. Each API call publishes a new
        Run command and returns a fresh run_id.
        """
        conv_response = await client.post(
            "/conversations",
            json={"title": "idempotency test"},
            headers={"X-User-ID": "1001", "X-Project-ID": "2001"},
        )
        conv_id = conv_response.json()["conversation_id"]

        body = {
            "type": "message",
            "content": "test",
            "metadata": {"request_id": "idempotent-req-001"},
        }

        response1 = await client.post(f"/conversations/{conv_id}/messages", json=body)
        response2 = await client.post(f"/conversations/{conv_id}/messages", json=body)

        assert response1.status_code == 200
        assert response2.status_code == 200
        # Each call returns a valid run_id (idempotency handled by Worker)
        assert "run_id" in response1.json()
        assert "run_id" in response2.json()

    async def test_list_messages(self, client: AsyncClient):
        """Listing messages returns the conversation's message history.

        Messages are stored by the Worker; for this test we insert
        directly via the async engine to verify the list endpoint.
        """
        conv_response = await client.post(
            "/conversations",
            json={"title": "list test"},
            headers={"X-User-ID": "1001", "X-Project-ID": "2001"},
        )
        conv_id = conv_response.json()["conversation_id"]

        # Insert messages directly (simulating Worker-persisted messages)
        from sqlalchemy import insert

        import app.persistence.engine as engine_module
        from app.persistence.models import Message

        engine = engine_module.get_engine()
        async with engine.begin() as conn:
            await conn.execute(
                insert(Message).values([
                    {
                        "id": f"msg-{i}",
                        "conversation_id": conv_id,
                        "run_id": f"run-{i}",
                        "role": "user",
                        "type": "message",
                        "content": f"message {i}",
                        "metadata_json": {},
                    }
                    for i in range(3)
                ])
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
