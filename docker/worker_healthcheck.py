"""Worker health check script for Docker.

Checks if the worker process is alive by:
1. Reading the PID file written by worker_entrypoint.py
2. Checking if that PID is still running using os.kill(pid, 0)
3. Reading OutboxPublisher health stats from a JSON file

Exit codes:
    0 - healthy (worker process found and alive)
    1 - unhealthy (worker process not found or dead)
"""

from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from typing import Any


def check_pid_file() -> bool:
    """Check if the PID file exists and the process is alive."""
    pid_file = os.environ.get("WORKER_PID_FILE", "/tmp/wisecut-agent-worker.pid")
    if not os.path.exists(pid_file):
        return False
    try:
        with open(pid_file) as f:
            pid = int(f.read().strip())
        os.kill(pid, 0)
        return True
    except (OSError, ValueError):
        return False


def check_process_by_name() -> bool:
    """Fallback: check if a process matching worker_entrypoint is running.

    Uses /proc filesystem (Linux only) to avoid external dependencies.
    """
    try:
        for entry in os.listdir("/proc"):
            if not entry.isdigit():
                continue
            try:
                cmdline_path = f"/proc/{entry}/cmdline"
                with open(cmdline_path, "rb") as f:
                    cmdline = f.read().decode("utf-8", errors="replace")
                if "worker_entrypoint" in cmdline:
                    return True
            except (OSError, PermissionError):
                continue
    except Exception:
        pass
    return False


def check_outbox_health() -> dict[str, Any]:
    """Check OutboxPublisher health from its stats file.

    Returns health status dict with publisher_running and healthy flags.
    """
    health_file = os.environ.get(
        "OUTBOX_HEALTH_FILE", "/tmp/wisecut-agent-outbox-health.json"
    )
    if not os.path.exists(health_file):
        return {"publisher_running": False, "healthy": False, "error": "health file not found"}

    try:
        with open(health_file) as f:
            stats = json.load(f)
        age_seconds = 0
        if stats.get("last_publish_at"):
            last_publish = datetime.fromisoformat(stats["last_publish_at"])
            age_seconds = (datetime.now(UTC) - last_publish).total_seconds()

        # Consider healthy if publisher is running and last publish was within 2x interval
        interval = stats.get("interval_seconds", 5)
        is_healthy = (
            stats.get("running", False)
            and age_seconds < interval * 2
        )
        return {
            "publisher_running": stats.get("running", False),
            "healthy": is_healthy,
            "last_publish_at": stats.get("last_publish_at"),
            "last_publish_count": stats.get("last_publish_count"),
            "age_seconds": age_seconds,
        }
    except (json.JSONDecodeError, KeyError, ValueError):
        return {"publisher_running": False, "healthy": False, "error": "invalid health file"}


if __name__ == "__main__":
    process_alive = check_pid_file() or check_process_by_name()
    outbox_health = check_outbox_health()

    if not process_alive:
        print(f"UNHEALTHY: worker process not found. outbox={outbox_health}")
        sys.exit(1)

    if not outbox_health.get("healthy", False):
        print(f"UNHEALTHY: outbox publisher unhealthy. status={outbox_health}")
        sys.exit(1)

    print(f"HEALTHY: worker alive. outbox={outbox_health}")
    sys.exit(0)
