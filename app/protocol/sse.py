"""SSE protocol helpers matching the Go Client's wire contract.

Go Client reference: internal/third_party/maa/agent/client.go
  - scanAgentFilmSSE
  - isAgentFilmTerminalEventType
  - parseMAAAgentFilmEvent
"""

from __future__ import annotations

import json
from typing import Any


# ---------------------------------------------------------------------------
# Terminal event detection
# ---------------------------------------------------------------------------

TERMINAL_EVENT_TYPES: frozenset[str] = frozenset(
    {"run.completed", "run.failed", "run.cancelled"}
)


def is_terminal_event(event_type: str) -> bool:
    """Return True if this event type terminates the SSE stream.

    Mirrors the Go Client's ``isAgentFilmTerminalEventType``.
    """
    return event_type in TERMINAL_EVENT_TYPES


# ---------------------------------------------------------------------------
# Seq extraction (mirrors parseMAAAgentFilmEvent priority)
# ---------------------------------------------------------------------------

def extract_seq(sse_id: str, event_type: str, data: str) -> int:
    """Extract sequence number following the Go Client's priority:

    1. data.payload.seq
    2. data.payload.sequence
    3. SSE ``id`` field parsed as int
    4. 0 (fallback)
    """
    # Try payload.seq first
    try:
        raw = json.loads(data) if data else {}
    except (json.JSONDecodeError, TypeError):
        raw = {}

    seq = _int_from_any(raw.get("seq"))
    if seq:
        return seq

    seq = _int_from_any(raw.get("sequence"))
    if seq:
        return seq

    # Fallback: try SSE id as int
    if sse_id:
        seq = _int_from_any(sse_id)
        if seq:
            return seq

    return 0


def _int_from_any(value: Any) -> int | None:
    """Best-effort int conversion matching Go Client's int64FromAny."""
    if value is None:
        return None
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, float):
        if value == int(value):
            return int(value)
        return None
    if isinstance(value, str):
        try:
            return int(value.strip())
        except (ValueError, TypeError):
            return None
    return None


# ---------------------------------------------------------------------------
# after_seq clamping (Go Client: if afterSeq < 0 { afterSeq = 0 })
# ---------------------------------------------------------------------------

def clamp_after_seq(after_seq: int) -> int:
    """Clamp after_seq to minimum 0."""
    return max(0, after_seq)


# ---------------------------------------------------------------------------
# Event envelope parsing (mirrors parseMAAAgentFilmEvent)
# ---------------------------------------------------------------------------

class ParsedEvent:
    """Parsed MAA event with resolved id, seq, type, and payload."""

    def __init__(
        self,
        event_id: str,
        event_type: str,
        data: str,
    ) -> None:
        self.raw_id = event_id
        self.raw_type = event_type
        self.raw_data = data

        # Resolve type
        self.type = event_type or "message"
        if not self.type:
            try:
                raw = json.loads(data) if data else {}
                self.type = str(raw.get("event_type", raw.get("type", "message"))).strip()
            except (json.JSONDecodeError, TypeError):
                pass
            if not self.type:
                self.type = "message"

        # Resolve id
        self.id = event_id
        if not self.id:
            try:
                raw = json.loads(data) if data else {}
                self.id = str(raw.get("event_id", "")).strip()
            except (json.JSONDecodeError, TypeError):
                pass

        # Resolve seq
        self.seq = extract_seq(self.id, self.type, data)

        # Resolve payload
        try:
            raw = json.loads(data) if data else {}
        except (json.JSONDecodeError, TypeError):
            raw = {}

        payload = raw.get("payload", {})
        if not isinstance(payload, dict):
            payload = {}

        if not payload:
            # No nested payload: use raw as payload, but exclude meta keys
            payload = {k: v for k, v in raw.items() if k not in ("seq", "sequence", "event_id", "event_type", "type")}

        # Merge top-level stage/thread_id into payload (Go Client behavior)
        for key in ("stage", "thread_id"):
            if key in raw and key not in payload:
                payload[key] = raw[key]

        self.payload = payload


def encode_sse_event(event_id: str, event_type: str, data: dict[str, Any]) -> str:
    """Encode an SSE event matching the Go Client's expected format."""
    lines = [
        f"id: {event_id}",
        f"event: {event_type}",
        f"data: {json.dumps(data, ensure_ascii=False)}",
        "",  # blank line terminates
    ]
    return "\n".join(lines)


def decode_sse_events(raw: str) -> list[dict[str, str]]:
    """Decode SSE events from raw text, matching Go Client's scanAgentFilmSSE."""
    events: list[dict[str, str]] = []
    current_id = ""
    current_event = ""
    current_data_lines: list[str] = []

    for line in raw.split("\n"):
        if line == "":
            if current_event or current_data_lines:
                events.append({
                    "id": current_id,
                    "event": current_event,
                    "data": "\n".join(current_data_lines),
                })
            current_id = ""
            current_event = ""
            current_data_lines = []
            continue
        if line.startswith(":"):
            continue  # comment/heartbeat
        key, sep, value = line.partition(":")
        if not sep:
            continue
        value = value.lstrip(" ")
        if key == "id":
            current_id = value
        elif key == "event":
            current_event = value
        elif key == "data":
            current_data_lines.append(value)

    return events
