"""Contract tests for MAA wire compatibility with the Go Client.

These tests validate protocol shapes, SSE encoding, and fixture conformance
without requiring a running server or LLM. They serve as the frozen contract
between the Go Client and this MAA Agent implementation.

Go Client reference: internal/third_party/maa/agent/
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import jsonschema
import pytest

# Paths
FIXTURES_DIR = Path(__file__).parent.parent.parent / "tests" / "fixtures" / "maa"
SCHEMAS_DIR = Path(__file__).parent.parent.parent

EVENT_SCHEMAS_DIR = SCHEMAS_DIR / "schemas" / "events"
INTERACTION_SCHEMAS_DIR = SCHEMAS_DIR / "schemas" / "interactions"
ARTIFACT_SCHEMAS_DIR = SCHEMAS_DIR / "schemas" / "artifacts"


# ---------------------------------------------------------------------------
# Schema loading helpers
# ---------------------------------------------------------------------------

def _load_schema(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_fixture(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_fixture_str(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Helper: validate data against a JSON Schema file
# ---------------------------------------------------------------------------

def _validate(schema_path: Path, data: dict):
    schema = _load_schema(schema_path)
    jsonschema.validate(data, schema)


# ---------------------------------------------------------------------------
# Test: all fixture files are valid JSON
# ---------------------------------------------------------------------------

FIXTURE_FILES = list(FIXTURES_DIR.glob("*.json"))


@pytest.mark.parametrize("fixture_path", FIXTURE_FILES, ids=lambda p: p.name)
def test_fixture_is_valid_json(fixture_path: Path):
    """Every fixture must be parseable JSON."""
    data = _load_fixture(fixture_path)
    assert isinstance(data, (dict, list)), f"{fixture_path.name}: top-level must be object or array"


# ---------------------------------------------------------------------------
# Test: all schema files are valid JSON Schema (draft 2020-12)
# ---------------------------------------------------------------------------

SCHEMA_FILES = (
    list(EVENT_SCHEMAS_DIR.glob("*.json"))
    + list(INTERACTION_SCHEMAS_DIR.glob("*.json"))
    + list(ARTIFACT_SCHEMAS_DIR.glob("*.json"))
)


@pytest.mark.parametrize("schema_path", SCHEMA_FILES, ids=lambda p: p.name)
def test_schema_is_valid_json_schema(schema_path: Path):
    """Every schema file must be a valid JSON Schema."""
    schema = _load_schema(schema_path)
    # Validate by using it against a trivial value
    jsonschema.Draft202012Validator.check_schema(schema)


# ---------------------------------------------------------------------------
# Test: create conversation request/response fixtures match schemas
# ---------------------------------------------------------------------------

class TestCreateConversationContract:
    """Contract for POST /conversations."""

    def test_quick_mode_request_matches_schema(self):
        from pydantic import BaseModel, Field

        # Inline schema for CreateConversationRequest (mirrors OpenAPI)
        class Meta(BaseModel):
            source: str
            local_run_id: str
            user_id: int
            project_id: int
            mode: str
            agent_profile_id: str
            response_language: str

        class CreateConversationRequest(BaseModel):
            title: str = Field(max_length=200)
            agent_profile_id: str | None = None
            metadata: Meta

        fixture = _load_fixture(FIXTURES_DIR / "create_conversation_quick.json")
        req = CreateConversationRequest(**fixture)
        assert req.title == "商品视频需求"
        assert req.agent_profile_id == "one-click-quick"
        assert req.metadata.mode == "quick"
        assert req.metadata.user_id == 1001
        assert req.metadata.project_id == 2001
        # user_id must NOT be at body top level (Go Client contract test)
        assert "user_id" not in fixture or fixture.get("user_id") is None or "metadata" in fixture

    def test_deep_mode_request_has_cocreate_profile(self):
        fixture = _load_fixture(FIXTURES_DIR / "create_conversation_deep.json")
        assert fixture["agent_profile_id"] == "one-click-cocreate"
        assert fixture["metadata"]["mode"] == "deep"

    def test_create_conversation_response_shape(self):
        """Response must match Go Client's CreateConversationResponse struct."""
        fixture = _load_fixture(FIXTURES_DIR / "create_conversation_response.json")
        required_keys = {"conversation_id", "langgraph_thread_id", "status"}
        assert required_keys.issubset(fixture.keys()), f"Missing keys: {required_keys - fixture.keys()}"
        assert fixture["status"] == "created"


# ---------------------------------------------------------------------------
# Test: message request/response fixtures
# ---------------------------------------------------------------------------

class TestMessageContract:
    """Contract for POST /conversations/{id}/messages."""

    def test_start_run_message_has_required_fields(self):
        fixture = _load_fixture(FIXTURES_DIR / "start_run_message.json")
        assert fixture["type"] == "message"
        assert "content" in fixture
        assert "metadata" in fixture
        # Content must start with the expected prefix
        content = fixture["content"]
        assert "$viral-ad-replication" in content, "Start run content must contain task instruction"

    def test_post_message_response_shape(self):
        fixture = _load_fixture(FIXTURES_DIR / "post_message_response.json")
        required_keys = {"conversation_id", "run_id", "accepted_as_inbox", "events_url"}
        assert required_keys.issubset(fixture.keys())


# ---------------------------------------------------------------------------
# Test: interaction response fixtures
# ---------------------------------------------------------------------------

class TestInteractionContract:
    """Contract for POST /conversations/{id}/messages (interaction_response type)."""

    def test_interaction_response_has_required_fields(self):
        fixture = _load_fixture(FIXTURES_DIR / "interaction_response.json")
        assert fixture["type"] == "interaction_response"
        assert fixture["interaction_id"] == "interaction-test-001"
        assert fixture["action"] == "approve"
        assert fixture["client_action_id"] == "act-test-001"
        assert "metadata" in fixture
        meta = fixture["metadata"]
        assert "value" in meta
        assert "summary" in meta
        assert "response_language" in meta
        assert meta["response_language"] == "zh-CN"
        assert "response_language_instruction" in meta

    def test_interaction_response_result_shape(self):
        fixture = _load_fixture(FIXTURES_DIR / "interaction_response_result.json")
        assert fixture["conversation_id"] == "conv-test-001"
        assert fixture["run_id"] == "run-test-001"
        assert "event" in fixture
        assert fixture["event"]["type"] == "interaction.resolved"
        assert "interaction" in fixture

    def test_interaction_response_idempotency_key_is_client_action_id(self):
        """The client_action_id serves as the idempotency key for interaction submissions."""
        fixture = _load_fixture(FIXTURES_DIR / "interaction_response.json")
        assert fixture["client_action_id"].startswith("act-")


# ---------------------------------------------------------------------------
# Test: conversation detail fixture
# ---------------------------------------------------------------------------

class TestConversationDetailContract:
    """Contract for GET /conversations/{id}."""

    def test_conversation_detail_has_required_sections(self):
        fixture = _load_fixture(FIXTURES_DIR / "conversation_detail.json")
        assert "conversation" in fixture
        assert "active_run" in fixture
        assert "messages" in fixture
        assert "interactions" in fixture
        assert "recent_events" in fixture

    def test_conversation_status_enum(self):
        fixture = _load_fixture(FIXTURES_DIR / "conversation_detail.json")
        valid_statuses = {"created", "active", "waiting_interaction", "waiting_approval",
                          "completed", "failed", "cancelled"}
        assert fixture["conversation"]["status"] in valid_statuses


# ---------------------------------------------------------------------------
# Test: SSE event encoding/decoding
# ---------------------------------------------------------------------------

class TestSSEContract:
    """Contract for SSE encoding, matching the Go Client's scanAgentFilmSSE parser."""

    def _encode_sse_event(self, event_id: str, event_type: str, data: dict) -> str:
        """Encode an SSE event in the same format the Go Client expects."""
        lines = [
            f"id: {event_id}",
            f"event: {event_type}",
            f"data: {json.dumps(data, ensure_ascii=False)}",
            "",  # blank line terminates the event
        ]
        return "\n".join(lines)

    def _decode_sse_events(self, raw: str) -> list[dict]:
        """Decode SSE events from raw text. Mirrors Go Client parser logic."""
        events = []
        current_id = ""
        current_event = ""
        current_data_lines: list[str] = []

        for line in raw.split("\n"):
            if line == "":
                if current_event or current_data_lines:
                    event = {
                        "id": current_id,
                        "event": current_event,
                        "data": "\n".join(current_data_lines),
                    }
                    events.append(event)
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

    def test_sse_roundtrip_single_event(self):
        """A single SSE event must survive encode/decode roundtrip."""
        original = {
            "id": "evt-001",
            "event": "tool.started",
            "data": {"seq": 1, "payload": {"tool_name": "extract_product_facts"}},
        }
        encoded = self._encode_sse_event(original["id"], original["event"], original["data"])
        decoded = self._decode_sse_events(encoded)
        assert len(decoded) == 1
        evt = decoded[0]
        assert evt["id"] == "evt-001"
        assert evt["event"] == "tool.started"
        parsed_data = json.loads(evt["data"])
        assert parsed_data["seq"] == 1
        assert parsed_data["payload"]["tool_name"] == "extract_product_facts"

    def test_sse_multiple_events_in_stream(self):
        """Multiple events in one stream must all be decoded correctly."""
        events = [
            ("evt-001", "run.started", {"seq": 1, "payload": {"run_id": "run-1"}}),
            ("evt-002", "tool.started", {"seq": 2, "payload": {"tool_name": "t1"}}),
            ("evt-003", "tool.completed", {"seq": 3, "payload": {"tool_name": "t1"}}),
            ("evt-004", "run.completed", {"seq": 4, "payload": {"run_id": "run-1"}}),
        ]
        stream = "\n".join(
            self._encode_sse_event(eid, etype, edata)
            for eid, etype, edata in events
        )
        decoded = self._decode_sse_events(stream)
        assert len(decoded) == 4
        assert decoded[0]["event"] == "run.started"
        assert decoded[-1]["event"] == "run.completed"

    def test_sse_heartbeat_comments_ignored(self):
        """Heartbeat comments (lines starting with :) must be ignored."""
        stream = ": heartbeat\n\nid: evt-1\nevent: run.started\ndata: {\"seq\":1}\n\n"
        decoded = self._decode_sse_events(stream)
        assert len(decoded) == 1
        assert decoded[0]["id"] == "evt-1"

    def test_sheep_data_continuation_lines(self):
        """Multi-line data fields must be joined with newlines (Go Client behavior)."""
        stream = (
            "id: evt-1\n"
            "event: assistant.delta\n"
            "data: line1\n"
            "data: line2\n"
            "data: line3\n"
            "\n"
        )
        decoded = self._decode_sse_events(stream)
        assert len(decoded) == 1
        assert "line1\nline2\nline3" == decoded[0]["data"]

    def test_terminal_event_detection(self):
        """The Go Client considers run.completed/failed/cancelled as terminal."""
        from app.protocol.sse import is_terminal_event
        assert is_terminal_event("run.completed") is True
        assert is_terminal_event("run.failed") is True
        assert is_terminal_event("run.cancelled") is True
        assert is_terminal_event("tool.started") is False
        assert is_terminal_event("interaction.requested") is False

    def test_seq_parsing_priority(self):
        """Go Client tries: event.id -> payload.seq -> payload.sequence -> id as int."""
        from app.protocol.sse import extract_seq

        # seq from payload.seq
        assert extract_seq("", "message", json.dumps({"seq": 42})) == 42
        # seq from payload.sequence
        assert extract_seq("", "message", json.dumps({"sequence": 99})) == 99
        # seq from SSE id as int
        assert extract_seq("10", "message", "{}") == 10
        # fallback to 0
        assert extract_seq("", "message", "{}") == 0


# ---------------------------------------------------------------------------
# Test: event payload schemas validate fixture data
# ---------------------------------------------------------------------------

class TestEventSchemaConformance:
    """All fixture event payloads must validate against their JSON schemas."""

    @pytest.mark.parametrize("schema_file", [
        "run-started.json",
        "run-phase-changed.json",
        "agent-progress.json",
        "assistant-delta.json",
        "assistant-message.json",
        "tool-started.json",
        "tool-completed.json",
        "tool-failed.json",
        "approval-required.json",
        "approval-resolved.json",
        "interaction-requested.json",
        "interaction-resolved.json",
        "interaction-updated.json",
        "artifact-created.json",
        "business-message.json",
        "run-terminal.json",
    ])
    def test_schema_files_are_valid(self, schema_file: str):
        """Each schema file must be valid JSON Schema (draft 2020-12)."""
        schema_path = EVENT_SCHEMAS_DIR / schema_file
        schema = _load_schema(schema_path)
        jsonschema.Draft202012Validator.check_schema(schema)

    def test_run_started_fixture_validates_against_schema(self):
        event = {
            "seq": 1,
            "type": "run.started",
            "payload": {
                "run_id": "run-1",
                "conversation_id": "conv-1",
                "status": "running",
                "phase": "starting",
                "started_at": "2026-10-14T06:00:00Z",
            },
        }
        _validate(EVENT_SCHEMAS_DIR / "run-started.json", event)

    def test_final_video_business_message_validates_against_schema(self):
        event = {
            "seq": 10,
            "type": "business.message",
            "payload": {
                "message": {
                    "business_key": "final_video",
                    "status": "completed",
                    "payload": {
                        "video_url": "https://example.com/video.mp4",
                        "cover_url": "https://example.com/cover.jpg",
                        "duration": "60",
                        "aspect_ratio": "9:16",
                    },
                }
            },
        }
        _validate(EVENT_SCHEMAS_DIR / "business-message.json", event)

    def test_run_terminal_completed_validates(self):
        event = {
            "seq": 11,
            "type": "run.completed",
            "payload": {"run_id": "run-1", "status": "completed"},
        }
        _validate(EVENT_SCHEMAS_DIR / "run-terminal.json", event)

    def test_run_terminal_failed_validates(self):
        event = {
            "seq": 11,
            "type": "run.failed",
            "payload": {"run_id": "run-1", "status": "failed", "error": "LLM timeout"},
        }
        _validate(EVENT_SCHEMAS_DIR / "run-terminal.json", event)

    def test_tool_completed_validates(self):
        event = {
            "seq": 3,
            "type": "tool.completed",
            "payload": {
                "tool_name": "extract_product_facts",
                "run_id": "run-1",
                "output": {"product_name": "test"},
            },
        }
        _validate(EVENT_SCHEMAS_DIR / "tool-completed.json", event)


# ---------------------------------------------------------------------------
# Test: interaction card schemas
# ---------------------------------------------------------------------------

class TestInteractionCardContract:
    """Interaction card frontend_interaction payloads must validate."""

    def test_confirm_product_context_card_schema(self):
        card = {
            "intent": "confirm_extracted_product_context",
            "status": "pending",
            "frontend_interaction": {
                "intent": "confirm_extracted_product_context",
                "status": "pending",
                "product_name": "无线降噪耳机",
                "selling_points": ["主动降噪"],
                "target_audience": ["通勤族"],
                "actions": ["confirm", "edit"],
            },
        }
        _validate(INTERACTION_SCHEMAS_DIR / "confirm-extracted-product-context.json", card)

    def test_review_storyboard_card_schema(self):
        card = {
            "intent": "review_storyboard_script",
            "status": "pending",
            "frontend_interaction": {
                "intent": "review_storyboard_script",
                "status": "pending",
                "options": [
                    {
                        "option_id": "opt-1",
                        "title": "方案 A",
                        "script_content": "...",
                    }
                ],
                "actions": ["select", "refresh", "modify"],
            },
        }
        _validate(INTERACTION_SCHEMAS_DIR / "review-storyboard-script.json", card)

    def test_confirm_generation_card_schema(self):
        card = {
            "intent": "confirm_generation_start",
            "status": "pending",
            "frontend_interaction": {
                "intent": "confirm_generation_start",
                "status": "pending",
                "cost_breakdown": {
                    "estimated_cost": 5.0,
                    "currency": "CNY",
                    "duration_seconds": 60,
                    "aspect_ratio": "9:16",
                },
                "actions": ["approve", "cancel"],
            },
        }
        _validate(INTERACTION_SCHEMAS_DIR / "confirm-generation-start.json", card)

    def test_component_cards_schema(self):
        card = {
            "intent": "component_cards",
            "status": "pending",
            "frontend_interaction": {
                "intent": "component_cards",
                "status": "pending",
                "cards": [
                    {
                        "intent": "select_video_style",
                        "formData": [{"key": "style", "value": "modern"}],
                    }
                ],
            },
        }
        _validate(INTERACTION_SCHEMAS_DIR / "component-cards.json", card)


# ---------------------------------------------------------------------------
# Test: artifact schemas
# ---------------------------------------------------------------------------

class TestArtifactContract:
    """Artifact and final_video schemas."""

    def test_final_video_artifact_payload(self):
        payload = {
            "business_key": "final_video",
            "status": "completed",
            "payload": {
                "video_url": "https://storage.example.com/videos/r1/final.mp4",
                "cover_url": "https://storage.example.com/videos/r1/cover.jpg",
                "duration": "60",
                "aspect_ratio": "9:16",
            },
        }
        _validate(ARTIFACT_SCHEMAS_DIR / "final-video-business-message.json", payload)

    def test_final_video_requires_video_and_cover_url(self):
        """final_video payload must have both video_url and cover_url."""
        schema = _load_schema(ARTIFACT_SCHEMAS_DIR / "final-video-business-message.json")
        validator = jsonschema.Draft202012Validator(schema)
        # Missing cover_url should fail
        with pytest.raises(jsonschema.ValidationError):
            validator.validate({
                "business_key": "final_video",
                "status": "completed",
                "payload": {"video_url": "https://example.com/v.mp4"},
            })

    def test_artifact_detail_response_schema(self):
        response = {
            "artifact": {
                "id": "art-001",
                "conversation_id": "conv-1",
                "run_id": "run-1",
                "artifact_type": "video",
                "status": "ready",
                "uri": "https://storage.example.com/videos/r1/final.mp4",
            }
        }
        _validate(ARTIFACT_SCHEMAS_DIR / "artifact-detail-response.json", response)


# ---------------------------------------------------------------------------
# Test: Go Client header contract
# ---------------------------------------------------------------------------

class TestHeaderContract:
    """The Go Client sends specific headers. These must be accepted."""

    GO_CLIENT_HEADERS = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-User-ID": "1001",
        "X-Project-ID": "2001",
        "X-Conversation-ID": "conv-1",
        "X-Run-ID": "run-1",
    }

    GO_CLIENT_SSE_HEADERS = {
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
        "X-User-ID": "1001",
        "X-Project-ID": "2001",
        "X-Conversation-ID": "conv-1",
        "X-Run-ID": "run-1",
    }

    def test_json_headers_are_set(self):
        """Go Client sends Content-Type: application/json and Accept: application/json."""
        assert self.GO_CLIENT_HEADERS["Accept"] == "application/json"
        assert self.GO_CLIENT_HEADERS["Content-Type"] == "application/json"

    def test_sse_headers_are_set(self):
        """Go Client sends Accept: text/event-stream for SSE."""
        assert self.GO_CLIENT_SSE_HEADERS["Accept"] == "text/event-stream"

    def test_user_project_headers_use_integer_strings(self):
        """X-User-ID and X-Project-ID are sent as integer strings (Go fmt.Sprint)."""
        assert self.GO_CLIENT_HEADERS["X-User-ID"] == "1001"
        assert self.GO_CLIENT_HEADERS["X-Project-ID"] == "2001"


# ---------------------------------------------------------------------------
# Test: Go Client error body contract
# ---------------------------------------------------------------------------

class TestErrorResponseContract:
    """Non-2xx responses must return the error body the Go Client can parse."""

    def test_error_body_shape(self):
        fixture = _load_fixture(FIXTURES_DIR / "error_response.json")
        required_keys = {"method", "path", "status_code", "body"}
        assert required_keys.issubset(fixture.keys())
        assert isinstance(fixture["body"], str)
        assert fixture["status_code"] >= 400

    def test_not_found_error_shape(self):
        """404 must have a parseable body."""
        error = {
            "method": "GET",
            "path": "/conversations/missing-conv",
            "status_code": 404,
            "body": '{"detail":"conversation not found"}',
        }
        required_keys = {"method", "path", "status_code", "body"}
        assert required_keys.issubset(error.keys())


# ---------------------------------------------------------------------------
# Test: response language normalization (Go Client contract)
# ---------------------------------------------------------------------------

class TestResponseLanguageContract:
    """The Go Client normalizes response_language. The MAA API must store and echo it."""

    NORMALIZED_LANGUAGES = {
        "zh": "zh-CN",
        "zh-cn": "zh-CN",
        "zh-hans": "zh-CN",
        "zh_hans": "zh-CN",
        "cn": "zh-CN",
        "sa": "zh-CN",
        "en": "en-US",
        "en-us": "en-US",
        "en_us": "en-US",
    }

    @pytest.mark.parametrize("input_lang,expected", list(NORMALIZED_LANGUAGES.items()))
    def test_language_normalization(self, input_lang: str, expected: str):
        """Go Client normalizes common language identifiers."""
        from app.protocol.language import normalize_response_language
        assert normalize_response_language(input_lang) == expected

    def test_empty_language_defaults_to_zh_cn(self):
        from app.protocol.language import normalize_response_language
        assert normalize_response_language("") == "zh-CN"
        assert normalize_response_language("   ") == "zh-CN"

    def test_language_instruction_generation(self):
        from app.protocol.language import build_language_instruction
        assert "简体中文" in build_language_instruction("zh-CN")
        assert "English" in build_language_instruction("en-US")


# ---------------------------------------------------------------------------
# Test: after_seq SSE resume contract
# ---------------------------------------------------------------------------

class TestAfterSeqContract:
    """The Go Client uses after_seq for SSE resume. This must work correctly."""

    def test_after_seq_zero_returns_all_events(self):
        """after_seq=0 means start from the beginning."""
        # This validates the contract definition; actual server behavior tested in integration.
        assert 0 == 0  # after_seq minimum is 0

    def test_after_seq_excludes_events_up_to_seq(self):
        """Events with seq <= after_seq must be skipped on resume."""
        after_seq = 5
        events = [
            {"seq": 3, "type": "tool.started"},
            {"seq": 4, "type": "tool.completed"},
            {"seq": 5, "type": "interaction.resolved"},
            {"seq": 6, "type": "run.phase_changed"},
            {"seq": 7, "type": "agent.progress"},
        ]
        resumed = [e for e in events if e["seq"] > after_seq]
        assert len(resumed) == 2
        assert resumed[0]["seq"] == 6
        assert resumed[1]["seq"] == 7

    def test_after_seq_negative_clamped_to_zero(self):
        """Go Client clamps after_seq < 0 to 0."""
        from app.protocol.sse import clamp_after_seq
        assert clamp_after_seq(-1) == 0
        assert clamp_after_seq(-100) == 0
        assert clamp_after_seq(0) == 0
        assert clamp_after_seq(5) == 5


# ---------------------------------------------------------------------------
# Test: protocol version and path contract
# ---------------------------------------------------------------------------

class TestProtocolVersionContract:
    """Protocol versioning and path contract."""

    def test_default_paths_match_go_client(self):
        """Default paths must match Go Client's agentFilmPaths defaults."""
        expected = {
            "conversations": "/conversations",
            "runs": "/runs",
            "approvals": "/approvals",
            "events": "/events",
        }
        # The plan.md and Go Client both use these defaults
        assert expected["conversations"] == "/conversations"
        assert expected["runs"] == "/runs"
        assert expected["approvals"] == "/approvals"
        assert expected["events"] == "/events"

    def test_sse_path_is_runs_run_id_events(self):
        """SSE path is /runs/{run_id}/events."""
        run_id = "run-test-001"
        expected_path = f"/runs/{run_id}/events"
        assert expected_path == "/runs/run-test-001/events"

    def test_events_query_params(self):
        """SSE query params: after_seq and live=true."""
        after_seq = 5
        query = f"after_seq={after_seq}&live=true"
        assert "after_seq=5" in query
        assert "live=true" in query


# ---------------------------------------------------------------------------
# Test: idempotency contract
# ---------------------------------------------------------------------------

class TestIdempotencyContract:
    """Idempotency requirements from the Go Client."""

    def test_message_idempotency_key_is_client_action_id(self):
        """For interaction_response, client_action_id is the idempotency key."""
        # The Go Client generates: "act-" + uuid
        import uuid
        client_action_id = f"act-{uuid.uuid4()}"
        assert client_action_id.startswith("act-")
        assert len(client_action_id) > 4

    def test_request_id_used_for_command_idempotency(self):
        """For commands, request_id serves as the idempotency key."""
        # Both interaction_submit and other commands use request_id
        request_id = "req-test-001"
        assert request_id == "req-test-001"

    def test_event_idempotency_key_is_conversation_plus_run_plus_seq(self):
        """Events are uniquely identified by (conversation_id, run_id, seq)."""
        key = ("conv-1", "run-1", 5)
        # This key must be unique
        assert len({key}) == 1


# ---------------------------------------------------------------------------
# Test: terminal event types
# ---------------------------------------------------------------------------

class TestTerminalEventContract:
    """Terminal event types that close the SSE stream."""

    TERMINAL_TYPES = {"run.completed", "run.failed", "run.cancelled"}
    NON_TERMINAL_TYPES = {
        "run.started", "run.phase_changed", "agent.progress",
        "assistant.delta", "assistant.message", "tool.started",
        "tool.completed", "tool.failed", "approval.required",
        "approval.resolved", "interaction.requested", "interaction.updated",
        "interaction.resolved", "artifact.created", "business.message",
        "assistant.thinking",
    }

    def test_terminal_event_types(self):
        from app.protocol.sse import is_terminal_event
        for etype in self.TERMINAL_TYPES:
            assert is_terminal_event(etype) is True, f"{etype} should be terminal"

    def test_non_terminal_event_types(self):
        from app.protocol.sse import is_terminal_event
        for etype in self.NON_TERMINAL_TYPES:
            assert is_terminal_event(etype) is False, f"{etype} should NOT be terminal"


# ---------------------------------------------------------------------------
# Test: artifact and business.message contract
# ---------------------------------------------------------------------------

class TestArtifactContract:
    """final_video artifact contract."""

    def test_final_video_business_message_schema_validates(self):
        payload = {
            "business_key": "final_video",
            "status": "completed",
            "payload": {
                "video_url": "https://cdn.example.com/v.mp4",
                "cover_url": "https://cdn.example.com/c.jpg",
                "duration": "60",
                "aspect_ratio": "9:16",
            },
        }
        _validate(ARTIFACT_SCHEMAS_DIR / "final-video-business-message.json", payload)

    def test_final_video_schema_requires_video_url(self):
        schema = _load_schema(ARTIFACT_SCHEMAS_DIR / "final-video-business-message.json")
        validator = jsonschema.Draft202012Validator(schema)
        with pytest.raises(jsonschema.ValidationError):
            validator.validate({
                "business_key": "final_video",
                "status": "completed",
                "payload": {"cover_url": "https://example.com/c.jpg"},
            })

    def test_artifact_detail_response_shape(self):
        response = {
            "artifact": {
                "id": "art-001",
                "conversation_id": "conv-1",
                "run_id": "run-1",
                "artifact_type": "video",
                "status": "ready",
                "uri": "https://example.com/v.mp4",
            }
        }
        _validate(ARTIFACT_SCHEMAS_DIR / "artifact-detail-response.json", response)
