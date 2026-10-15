"""Unit tests for WP-05 Worker and recovery infrastructure."""

from __future__ import annotations

import os
import sys
from datetime import UTC
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


# ---------------------------------------------------------------------------
# LockManager tests
# ---------------------------------------------------------------------------


class TestConversationLock:
    async def test_acquire_lock_success(self):
        """Lock acquisition succeeds when no lock exists."""
        from app.worker.lock_manager import ConversationLock

        redis = AsyncMock()
        redis.get = AsyncMock(return_value=None)
        redis.set = AsyncMock(return_value=True)

        lock = await ConversationLock.acquire(redis, "conv-1", "run-1")
        assert lock is not None
        assert lock.run_id == "run-1"
        redis.set.assert_called_once()

    async def test_acquire_lock_fails_when_held(self):
        """Lock acquisition fails when another run holds the lock."""
        from app.worker.lock_manager import ConversationLock

        redis = AsyncMock()
        redis.get = AsyncMock(return_value=b'{"run_id": "run-other"}')
        redis.set = AsyncMock(return_value=False)  # NX: already exists

        lock = await ConversationLock.acquire(redis, "conv-1", "run-1")
        assert lock is None

    async def test_lock_heartbeat_extends_ttl(self):
        """Heartbeat extends the lock TTL."""
        from app.worker.lock_manager import ConversationLock

        redis = AsyncMock()
        redis.get = AsyncMock(return_value=True)

        lock = ConversationLock(redis, "conv-1", "run-1")
        await lock.heartbeat()
        redis.expire.assert_called_with(lock.key, lock._ttl)

    async def test_lock_release_clears_key(self):
        """Release deletes the lock key if held."""
        from app.worker.lock_manager import ConversationLock

        redis = AsyncMock()
        redis.get = AsyncMock(return_value=b'{"run_id": "run-1"}')

        lock = ConversationLock(redis, "conv-1", "run-1")
        await lock.release()
        redis.delete.assert_called_with(lock.key)

    async def test_lock_release_skips_if_held_by_other(self):
        """Release does NOT delete if another run holds the lock."""
        from app.worker.lock_manager import ConversationLock

        redis = AsyncMock()
        redis.get = AsyncMock(return_value=b'{"run_id": "run-other"}')

        lock = ConversationLock(redis, "conv-1", "run-1")
        await lock.release()
        redis.delete.assert_not_called()


# ---------------------------------------------------------------------------
# CancelController tests
# ---------------------------------------------------------------------------


class TestCancelController:
    async def test_request_cancel_sets_flag(self):
        from app.worker.cancel import CancelController

        redis = AsyncMock()
        redis.set = AsyncMock(return_value=True)

        cancel = CancelController(redis)
        await cancel.request_cancel("run-1")
        redis.set.assert_called_once()
        args = redis.set.call_args
        assert args[0][0] == "maa:cancel:run-1"
        assert args[1]["ex"] == 3600

    async def test_is_cancelled_true_when_set(self):
        from app.worker.cancel import CancelController

        redis = AsyncMock()
        redis.get = AsyncMock(return_value=b"1")

        cancel = CancelController(redis)
        assert await cancel.is_cancelled("run-1") is True

    async def test_is_cancelled_false_when_not_set(self):
        from app.worker.cancel import CancelController

        redis = AsyncMock()
        redis.get = AsyncMock(return_value=None)

        cancel = CancelController(redis)
        assert await cancel.is_cancelled("run-1") is False

    async def test_clear_cancel_deletes_key(self):
        from app.worker.cancel import CancelController

        redis = AsyncMock()
        redis.delete = AsyncMock(return_value=1)

        cancel = CancelController(redis)
        await cancel.clear_cancel("run-1")
        redis.delete.assert_called_once_with("maa:cancel:run-1")


# ---------------------------------------------------------------------------
# OutboxPublisher tests
# ---------------------------------------------------------------------------


class TestOutboxPublisher:
    async def test_publish_once_returns_zero_when_empty(self):
        from app.infra.outbox_publisher import OutboxPublisher

        factory = MagicMock()
        session = AsyncMock()
        factory.return_value.__aenter__ = AsyncMock(return_value=session)
        factory.return_value.__aexit__ = AsyncMock(return_value=None)
        repo = AsyncMock()
        repo.get_unpublished = AsyncMock(return_value=[])

        with patch("app.infra.outbox_publisher.get_session_factory", return_value=factory):
            with patch("app.infra.outbox_publisher.OutboxRepository", return_value=repo):
                publisher = OutboxPublisher()
                count = await publisher.publish_once()
                assert count == 0

    async def test_start_stop_lifecycle(self):
        from app.infra.outbox_publisher import OutboxPublisher

        publisher = OutboxPublisher(interval_seconds=60)
        await publisher.start()
        assert publisher._running is True
        assert publisher._task is not None
        await publisher.stop()
        assert publisher._running is False


# ---------------------------------------------------------------------------
# RunRecovery tests
# ---------------------------------------------------------------------------


class TestRunRecovery:
    async def test_scan_non_terminal_runs(self):
        from app.worker.run_recovery import scan_and_recover

        mock_run = MagicMock()
        mock_run.id = "run-queued"
        mock_run.status = "queued"  # Queued runs are retained, not recovered
        mock_run.started_at = None
        mock_run.conversation_id = "conv-1"

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_run]
        mock_execute = AsyncMock(return_value=mock_result)
        mock_commit = AsyncMock()
        mock_flush = AsyncMock()

        mock_session = MagicMock()
        mock_session.execute = mock_execute
        mock_session.commit = mock_commit
        mock_session.flush = mock_flush

        mock_factory = MagicMock()
        mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_factory.return_value.__aexit__ = AsyncMock(return_value=None)

        with patch("app.worker.run_recovery.get_session_factory", return_value=mock_factory):
            recovered = await scan_and_recover()

        assert len(recovered) == 1
        assert recovered[0]["run_id"] == "run-queued"
        assert recovered[0]["action"] == "retained"

    async def test_scan_resets_stuck_running_runs(self):
        from datetime import datetime

        from app.worker.run_recovery import scan_and_recover

        mock_run = MagicMock()
        mock_run.id = "run-stuck"
        mock_run.status = "running"
        # Started 2 hours ago → should be marked as failed
        two_hours_ago = datetime.now(UTC).timestamp() - 7200
        mock_run.started_at = datetime.fromtimestamp(two_hours_ago, tz=UTC)
        mock_run.conversation_id = "conv-1"

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_run]
        mock_execute = AsyncMock(return_value=mock_result)
        mock_commit = AsyncMock()
        mock_flush = AsyncMock()

        mock_session = MagicMock()
        mock_session.execute = mock_execute
        mock_session.commit = mock_commit
        mock_session.flush = mock_flush

        mock_factory = MagicMock()
        mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_factory.return_value.__aexit__ = AsyncMock(return_value=None)

        with patch("app.worker.run_recovery.get_session_factory", return_value=mock_factory):
            recovered = await scan_and_recover()

        # Stuck run should NOT be in recovered list (it was marked as failed)
        assert len(recovered) == 0


# ---------------------------------------------------------------------------
# RunWorker tests
# ---------------------------------------------------------------------------


class TestRunWorker:
    async def test_worker_initialization(self):
        from app.worker.run_worker import RunWorker

        handler = AsyncMock()
        worker = RunWorker(run_handler=handler, prefetch_count=2)
        assert worker._handler is handler
        assert worker._prefetch == 2
        assert worker._thread is None

    async def test_start_worker_thread(self):
        from app.worker.run_worker import RunWorker

        worker = RunWorker()
        worker.start()
        assert worker._thread is not None
        assert worker._thread.is_alive()
        worker.stop()

    async def test_stop_worker(self):
        from app.worker.run_worker import RunWorker

        worker = RunWorker()
        worker.start()
        import time
        time.sleep(0.5)  # Let thread start
        worker.stop()
        assert worker._thread is None or not worker._thread.is_alive()
