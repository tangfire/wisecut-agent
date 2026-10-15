"""Worker process entry point for wisecut-agent.

Runs as a separate Compose service (agent-worker) with its own event loop
and database connection pool, per plan.md section 10.1.

Usage:
    python -m docker.worker_entrypoint

Or directly:
    cd /app && python docker/worker_entrypoint.py
"""

from __future__ import annotations

import asyncio
import os
import signal
import sys
from typing import Any

# Ensure the application package is importable regardless of CWD
_APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

from app.settings import Settings  # noqa: E402
from app.worker.run_worker import RunWorker  # noqa: E402


def _write_pid_file() -> None:
    """Write the current process PID to a file for healthcheck."""
    pid_file = os.environ.get("WORKER_PID_FILE", "/tmp/wisecut-agent-worker.pid")
    try:
        with open(pid_file, "w") as f:
            f.write(str(os.getpid()))
    except Exception as exc:
        print(f"[worker] Failed to write PID file: {exc}", flush=True)


def _purge_dlq() -> None:
    """Purge stale messages from the DLQ on startup.

    Old test messages from previous failed runs should not block or
    accumulate in the DLQ across container restarts.
    """
    import pika

    params = pika.URLParameters(Settings().rabbitmq_url)
    conn = pika.BlockingConnection(params)
    try:
        ch = conn.channel()
        result = ch.queue_purge(queue="maa.run.commands.dlq")
        print(
            f"[worker] DLQ purged: {result.method.message_count} messages removed",
            flush=True,
        )
    except Exception as exc:
        print(f"[worker] DLQ purge failed: {exc}", flush=True)
    finally:
        conn.close()


def _build_handler(runner: Any) -> Any:
    """Build a RunWorker handler that delegates to GraphRunner.execute_run.

    Bridges the RunWorker calling convention
    (run_id, conversation_id, command_type, payload, loop)
    to GraphRunner.execute_run(run_id, conversation_id, lock, loop, interaction_response).
    """
    async def _handler(
        run_id: str,
        conversation_id: str,
        command_type: str,
        payload: dict[str, Any],
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        """Adapt RunWorker convention to GraphRunner.execute_run."""
        interaction_response = None
        if command_type == "interaction_response":
            interaction_response = {
                "interaction_id": payload.get("interaction_id", ""),
                "action": payload.get("action", ""),
                "content": payload.get("content", payload.get("payload", {})),
            }

        result = await runner.execute_run(
            run_id=run_id,
            conversation_id=conversation_id,
            loop=loop,
            interaction_response=interaction_response,
        )
        status = result.get("status", "") if isinstance(result, dict) else ""
        if status in ("failed", "error"):
            error_msg = result.get("error", "graph execution failed")
            raise RuntimeError(error_msg)

    return _handler


def main() -> None:
    """Entry point: set up event loop, run worker thread."""
    settings = Settings()
    settings.validate_or_exit()

    # Write PID file for healthcheck
    _write_pid_file()

    # Purge stale DLQ messages from previous runs
    _purge_dlq()

    # Create a dedicated event loop for this process (used for signal handling)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def _run() -> None:
        # Create a local DB session factory bound to THIS event loop.
        # This avoids the asyncpg "Future attached to a different loop" error
        # when the API process has already initialized the global factory
        # in a different event loop.
        from app.persistence.engine import create_local_session_factory
        local_factory = create_local_session_factory()

        # Create GraphRunner with the local session factory
        from app.graph.runner import GraphRunner
        runner = GraphRunner(session_factory=local_factory)

        # Build the handler that bridges RunWorker → GraphRunner
        handler = _build_handler(runner)

        # Create the Worker with the real GraphRunner handler
        worker = RunWorker(run_handler=handler)
        worker.start()
        print("[worker] Worker thread started", flush=True)

        # Wait for termination signal
        stop_event = asyncio.Event()

        def _signal_handler() -> None:
            print("[worker] Received shutdown signal", flush=True)
            stop_event.set()

        loop.add_signal_handler(signal.SIGTERM, _signal_handler)
        loop.add_signal_handler(signal.SIGINT, _signal_handler)

        try:
            await stop_event.wait()
        finally:
            print("[worker] Stopping worker thread...", flush=True)
            worker.stop()
            print("[worker] Shutdown complete", flush=True)

    try:
        loop.run_until_complete(_run())
    except KeyboardInterrupt:
        print("[worker] Interrupted", flush=True)
    finally:
        loop.close()


if __name__ == "__main__":
    main()
