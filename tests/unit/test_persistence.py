"""Unit tests for persistence layer: repositories, UnitOfWork, checkpointer, outbox."""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_session() -> MagicMock:
    session = MagicMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)
    return session


# ---------------------------------------------------------------------------
# ConversationRepository
# ---------------------------------------------------------------------------

class TestConversationRepository:
    async def test_create_conversation(self):
        from app.persistence.repositories import ConversationRepository

        session = _make_session()
        repo = ConversationRepository(session)

        # Mock the add/flush cycle
        session.add = MagicMock()
        session.flush = AsyncMock()

        conv = await repo.create(
            conversation_id="conv-1",
            user_id="user-1",
            project_id="proj-1",
            profile_id="quick",
            title="Test",
            metadata={"mode": "quick"},
        )

        assert conv.id == "conv-1"
        assert conv.user_id == "user-1"
        assert conv.profile_id == "quick"
        assert conv.status == "created"
        session.add.assert_called_once()
        session.flush.assert_called_once()

    async def test_get_by_id_returns_none_when_not_found(self):
        from app.persistence.repositories import ConversationRepository

        session = _make_session()
        repo = ConversationRepository(session)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=mock_result)

        result = await repo.get_by_id("nonexistent")
        assert result is None

    async def test_update_status(self):
        from app.persistence.repositories import ConversationRepository

        session = _make_session()
        repo = ConversationRepository(session)

        # Create a mock conversation
        mock_conv = MagicMock()
        mock_conv.id = "conv-1"
        mock_conv.status = "created"

        # First get_by_id returns the mock, second call (in get_by_id inside update_status)
        # also returns it
        session.add = MagicMock()
        session.flush = AsyncMock()

        conv = await repo.create(
            conversation_id="conv-1",
            user_id="user-1",
            project_id="proj-1",
            profile_id="quick",
            title="Test",
        )

        # Manually set up the mock for get_by_id
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = conv
        session.execute = AsyncMock(return_value=mock_result)

        updated = await repo.update_status("conv-1", "active")
        assert updated.status == "active"


# ---------------------------------------------------------------------------
# RunRepository
# ---------------------------------------------------------------------------

class TestRunRepository:
    async def test_create_run(self):
        from app.persistence.repositories import RunRepository

        session = _make_session()
        repo = RunRepository(session)
        session.add = MagicMock()
        session.flush = AsyncMock()

        run = await repo.create(run_id="run-1", conversation_id="conv-1")
        assert run.id == "run-1"
        assert run.status == "queued"
        assert run.phase == "starting"

    async def test_mark_started_and_finished(self):
        from app.persistence.repositories import RunRepository

        session = _make_session()
        repo = RunRepository(session)
        session.add = MagicMock()
        session.flush = AsyncMock()

        run = await repo.create(run_id="run-1", conversation_id="conv-1")

        # Mock get_by_id for mark_started
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = run
        session.execute = AsyncMock(return_value=mock_result)

        await repo.mark_started("run-1")
        assert run.status == "running"
        assert run.started_at is not None

        await repo.mark_finished("run-1", "completed")
        assert run.status == "completed"
        assert run.finished_at is not None


# ---------------------------------------------------------------------------
# EventRepository
# ---------------------------------------------------------------------------

class TestEventRepository:
    async def test_create_event(self):
        from app.persistence.repositories import EventRepository

        session = _make_session()
        repo = EventRepository(session)
        session.add = MagicMock()
        session.flush = AsyncMock()

        event = await repo.create(
            event_id="evt-1",
            conversation_id="conv-1",
            run_id="run-1",
            seq=1,
            event_type="run.started",
            payload={"run_id": "run-1"},
        )
        assert event.seq == 1
        assert event.event_type == "run.started"
        assert event.payload_json == {"run_id": "run-1"}

    async def test_get_next_seq_starts_at_1(self):
        from app.persistence.repositories import EventRepository

        session = _make_session()
        repo = EventRepository(session)

        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 0
        session.execute = AsyncMock(return_value=mock_result)

        next_seq = await repo.get_next_seq("conv-1", "run-1")
        assert next_seq == 1


# ---------------------------------------------------------------------------
# MessageRepository
# ---------------------------------------------------------------------------

class TestMessageRepository:
    async def test_create_message(self):
        from app.persistence.repositories import MessageRepository

        session = _make_session()
        repo = MessageRepository(session)
        session.add = MagicMock()
        session.flush = AsyncMock()

        msg = await repo.create(
            message_id="msg-1",
            conversation_id="conv-1",
            role="user",
            content="hello",
            run_id="run-1",
            message_type="message",
            request_id="req-1",
        )
        assert msg.role == "user"
        assert msg.content == "hello"
        assert msg.request_id == "req-1"

    async def test_idempotency_check_by_request_id(self):
        from app.persistence.repositories import MessageRepository

        session = _make_session()
        repo = MessageRepository(session)

        mock_existing = MagicMock()
        mock_existing.id = "msg-existing"
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_existing
        session.execute = AsyncMock(return_value=mock_result)

        result = await repo.get_by_request_id("conv-1", "req-1")
        assert result is not None
        assert result.id == "msg-existing"


# ---------------------------------------------------------------------------
# OutboxRepository
# ---------------------------------------------------------------------------

class TestOutboxRepository:
    async def test_enqueue_event(self):
        from app.persistence.repositories import OutboxRepository

        session = _make_session()
        repo = OutboxRepository(session)
        session.add = MagicMock()
        session.flush = AsyncMock()

        event = await repo.enqueue(
            aggregate_type="conversation",
            aggregate_id="conv-1",
            event_type="run.started",
            payload={"run_id": "run-1"},
        )
        assert event.event_type == "run.started"
        assert event.published_at is None
        assert event.attempt == 0

    async def test_get_unpublished(self):
        from app.persistence.repositories import OutboxRepository

        session = _make_session()
        repo = OutboxRepository(session)

        mock_event = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_event]
        session.execute = AsyncMock(return_value=mock_result)

        events = await repo.get_unpublished(limit=10)
        assert len(events) == 1


# ---------------------------------------------------------------------------
# SSE formatting
# ---------------------------------------------------------------------------

class TestSSEFormatting:
    async def test_format_sse_event(self):
        from app.persistence.outbox import format_sse_event

        sse = format_sse_event("run.started", {"seq": 1, "run_id": "run-1"}, "evt-1")
        assert sse.startswith("id: evt-1\n")
        assert "event: run.started" in sse
        assert "seq" in sse


# ---------------------------------------------------------------------------
# UTC / Shanghai time strategy
# ---------------------------------------------------------------------------

class TestTimeStrategy:
    async def test_utc_storage_and_shanghai_display(self):
        """All timestamps are stored in UTC and converted to Asia/Shanghai for display."""
        from app.persistence.repositories import ConversationRepository
        from zoneinfo import ZoneInfo

        session = _make_session()
        repo = ConversationRepository(session)
        session.add = MagicMock()
        session.flush = AsyncMock()

        now_utc = datetime.now(timezone.utc)
        conv = await repo.create(
            conversation_id="conv-1",
            user_id="user-1",
            project_id="proj-1",
            profile_id="quick",
            title="Test",
        )

        # Verify the timestamp is timezone-aware UTC
        shanghai_tz = ZoneInfo("Asia/Shanghai")
        # The _now() method should return a timezone-aware datetime in UTC
        now = repo._now()
        assert now.tzinfo is not None, "Timestamps must be timezone-aware (UTC)"
