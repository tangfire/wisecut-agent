"""Application metrics collector.

Collects metrics for:
  - HTTP request latency and status codes
  - LLM token usage and costs
  - Tool execution success/failure and latency
  - Run phase durations
  - SSE connection counts
  - Outbox queue depth
  - Active runs

Uses a simple in-memory store that can be exported to Prometheus format.
In production, these would be pushed to a metrics backend.
"""
from __future__ import annotations

import logging
import threading
from collections import defaultdict
from typing import Any

logger = logging.getLogger(__name__)


class _Histogram:
    """Simple histogram for latency measurements."""

    def __init__(self) -> None:
        self._values: list[float] = []
        self._lock = threading.Lock()

    def observe(self, value: float) -> None:
        with self._lock:
            self._values.append(value)

    @property
    def count(self) -> int:
        with self._lock:
            return len(self._values)

    @property
    def sum(self) -> float:
        with self._lock:
            return sum(self._values)

    @property
    def avg(self) -> float:
        with self._lock:
            if not self._values:
                return 0.0
            return sum(self._values) / len(self._values)

    def percentile(self, p: float) -> float:
        with self._lock:
            if not self._values:
                return 0.0
            sorted_vals = sorted(self._values)
            idx = int(len(sorted_vals) * p / 100)
            return sorted_vals[min(idx, len(sorted_vals) - 1)]


class _Counter:
    """Simple counter."""

    def __init__(self) -> None:
        self._value = 0
        self._lock = threading.Lock()

    def inc(self, amount: int = 1) -> None:
        with self._lock:
            self._value += amount

    @property
    def value(self) -> int:
        with self._lock:
            return self._value


class MetricsCollector:
    """Application-wide metrics collector.

    Thread-safe and designed for low overhead.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._http_latency = _Histogram()
        self._http_requests: dict[str, dict[str, _Counter]] = defaultdict(lambda: defaultdict(_Counter))
        self._llm_tokens = _Counter()
        self._llm_cost = _Histogram()
        self._tool_latency = _Histogram()
        self._tool_success = _Counter()
        self._tool_failure = _Counter()
        self._run_phases: dict[str, _Histogram] = defaultdict(_Histogram)
        self._sse_connections = _Counter()
        self._sse_reconnects = _Counter()
        self._outbox_depth = 0
        self._active_runs = 0
        self._active_sse_connections = 0

    # HTTP metrics

    def record_http_request(
        self, method: str, path: str, status_code: int, duration_ms: float
    ) -> None:
        """Record an HTTP request."""
        self._http_latency.observe(duration_ms)
        self._http_requests[path][str(status_code)].inc()

    # LLM metrics

    def record_llm_tokens(self, count: int) -> None:
        """Record LLM token usage."""
        self._llm_tokens.inc(count)

    def record_llm_cost(self, cost_usd: float) -> None:
        """Record LLM cost in USD."""
        self._llm_cost.observe(cost_usd)

    # Tool metrics

    def record_tool_execution(self, tool_name: str, success: bool, duration_ms: float) -> None:
        """Record a tool execution."""
        self._tool_latency.observe(duration_ms)
        if success:
            self._tool_success.inc()
        else:
            self._tool_failure.inc()

    # Run metrics

    def record_run_phase(self, phase: str, duration_ms: float) -> None:
        """Record a run phase duration."""
        self._run_phases[phase].observe(duration_ms)

    def set_active_runs(self, count: int) -> None:
        """Set current active run count."""
        with self._lock:
            self._active_runs = count

    # SSE metrics

    def record_sse_connection(self) -> None:
        self._sse_connections.inc()
        with self._lock:
            self._active_sse_connections += 1

    def record_sse_disconnect(self) -> None:
        with self._lock:
            self._active_sse_connections = max(0, self._active_sse_connections - 1)

    def record_sse_reconnect(self) -> None:
        self._sse_reconnects.inc()

    # Outbox metrics

    def set_outbox_depth(self, depth: int) -> None:
        with self._lock:
            self._outbox_depth = depth

    # Export

    def to_prometheus(self) -> str:
        """Export metrics in Prometheus text format."""
        lines = []
        lines.append("# HELP wisecut_agent_http_request_duration_seconds HTTP request latency")
        lines.append("# TYPE wisecut_agent_http_request_duration_seconds histogram")
        hist = self._http_latency
        lines.append(f"wisecut_agent_http_request_duration_seconds_sum {hist.sum / 1000:.6f}")
        lines.append(f"wisecut_agent_http_request_duration_seconds_count {hist.count}")

        lines.append("# HELP wisecut_agent_llm_tokens_total Total LLM tokens used")
        lines.append("# TYPE wisecut_agent_llm_tokens_total counter")
        lines.append(f"wisecut_agent_llm_tokens_total {self._llm_tokens.value}")

        lines.append("# HELP wisecut_agent_tool_executions_total Total tool executions")
        lines.append("# TYPE wisecut_agent_tool_executions_total counter")
        lines.append(f"wisecut_agent_tool_executions_total {self._tool_success.value + self._tool_failure.value}")

        lines.append("# HELP wisecut_agent_tool_failures_total Total tool failures")
        lines.append("# TYPE wisecut_agent_tool_failures_total counter")
        lines.append(f"wisecut_agent_tool_failures_total {self._tool_failure.value}")

        lines.append("# HELP wisecut_agent_active_runs Current active runs")
        lines.append("# TYPE wisecut_agent_active_runs gauge")
        lines.append(f"wisecut_agent_active_runs {self._active_runs}")

        lines.append("# HELP wisecut_agent_sse_connections_total Total SSE connections")
        lines.append("# TYPE wisecut_agent_sse_connections_total counter")
        lines.append(f"wisecut_agent_sse_connections_total {self._sse_connections.value}")

        lines.append("# HELP wisecut_agent_outbox_depth Current outbox queue depth")
        lines.append("# TYPE wisecut_agent_outbox_depth gauge")
        lines.append(f"wisecut_agent_outbox_depth {self._outbox_depth}")

        return "\n".join(lines) + "\n"

    def to_dict(self) -> dict[str, Any]:
        """Export metrics as a dict (for /metrics JSON endpoint)."""
        return {
            "http": {
                "latency_avg_ms": round(self._http_latency.avg, 2),
                "latency_p95_ms": round(self._http_latency.percentile(95), 2),
                "latency_p99_ms": round(self._http_latency.percentile(99), 2),
                "total_requests": self._http_latency.count,
            },
            "llm": {
                "total_tokens": self._llm_tokens.value,
                "cost_usd_total": round(self._llm_cost.sum, 6),
            },
            "tools": {
                "total_executions": self._tool_success.value + self._tool_failure.value,
                "successes": self._tool_success.value,
                "failures": self._tool_failure.value,
                "latency_avg_ms": round(self._tool_latency.avg, 2),
            },
            "runs": {
                "active": self._active_runs,
                "phases": {
                    phase: {
                        "count": h.count,
                        "avg_ms": round(h.avg, 2),
                    }
                    for phase, h in self._run_phases.items()
                },
            },
            "sse": {
                "active_connections": self._active_sse_connections,
                "total_connections": self._sse_connections.value,
                "total_reconnects": self._sse_reconnects.value,
            },
            "outbox": {
                "depth": self._outbox_depth,
            },
        }

    def reset(self) -> None:
        """Reset all metrics to zero. For testing only."""
        with self._lock:
            self._http_latency = _Histogram()
            self._http_requests.clear()
            self._llm_tokens = _Counter()
            self._llm_cost = _Histogram()
            self._tool_latency = _Histogram()
            self._tool_success = _Counter()
            self._tool_failure = _Counter()
            self._run_phases.clear()
            self._sse_connections = _Counter()
            self._sse_reconnects = _Counter()
            self._outbox_depth = 0
            self._active_runs = 0
            self._active_sse_connections = 0


# Global metrics collector
metrics = MetricsCollector()
