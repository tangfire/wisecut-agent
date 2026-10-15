"""Worker health check script for Docker.

Checks if the worker process is alive by:
1. Reading the PID file written by worker_entrypoint.py
2. Checking if that PID is still running using os.kill(pid, 0)

Exit codes:
    0 - healthy (worker process found and alive)
    1 - unhealthy (worker process not found or dead)
"""

from __future__ import annotations

import os
import sys


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


if __name__ == "__main__":
    alive = check_pid_file() or check_process_by_name()
    sys.exit(0 if alive else 1)
