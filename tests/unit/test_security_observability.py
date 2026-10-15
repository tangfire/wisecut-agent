"""Unit tests for WP-10 Security and Observability.

Covers:
  - SSRF guard (validate_external_url)
  - Authorization checks
  - File upload validation
  - Metrics collector
  - Rate limiter (basic)
  - Audit log repository
"""
from __future__ import annotations

import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


# ---------------------------------------------------------------------------
# SSRF Guard tests
# ---------------------------------------------------------------------------


class TestSSRFGuard:
    def test_https_url_passes(self):
        from app.security.ssrf import validate_external_url

        assert validate_external_url("https://example.com/video.mp4") == "https://example.com/video.mp4"

    def test_http_url_passes(self):
        from app.security.ssrf import validate_external_url

        assert validate_external_url("http://example.com/api") == "http://example.com/api"

    def test_empty_url_fails(self):
        from app.security.ssrf import SSRFValidationError, validate_external_url

        with pytest.raises(SSRFValidationError):
            validate_external_url("")

    def test_none_url_fails(self):
        from app.security.ssrf import SSRFValidationError, validate_external_url

        with pytest.raises(SSRFValidationError):
            validate_external_url(None)

    def test_no_protocol_fails(self):
        from app.security.ssrf import SSRFValidationError, validate_external_url

        with pytest.raises(SSRFValidationError):
            validate_external_url("ftp://example.com/file")

    def test_localhost_blocked(self):
        from app.security.ssrf import SSRFValidationError, validate_external_url

        with pytest.raises(SSRFValidationError):
            validate_external_url("http://localhost/video.mp4")

    def test_127_0_0_1_blocked(self):
        from app.security.ssrf import SSRFValidationError, validate_external_url

        with pytest.raises(SSRFValidationError):
            validate_external_url("http://127.0.0.1:8080/video.mp4")

    def test_ipv6_loopback_blocked(self):
        from app.security.ssrf import SSRFValidationError, validate_external_url

        with pytest.raises(SSRFValidationError):
            validate_external_url("http://[::1]/video.mp4")

    def test_zero_dot_zero_blocked(self):
        from app.security.ssrf import SSRFValidationError, validate_external_url

        with pytest.raises(SSRFValidationError):
            validate_external_url("http://0.0.0.0/video.mp4")

    def test_private_10_x_blocked(self):
        from app.security.ssrf import SSRFValidationError, validate_external_url

        with pytest.raises(SSRFValidationError):
            validate_external_url("http://10.0.0.1/internal")

    def test_private_172_16_x_blocked(self):
        from app.security.ssrf import SSRFValidationError, validate_external_url

        with pytest.raises(SSRFValidationError):
            validate_external_url("http://172.16.0.1/internal")

    def test_private_192_168_x_blocked(self):
        from app.security.ssrf import SSRFValidationError, validate_external_url

        with pytest.raises(SSRFValidationError):
            validate_external_url("http://192.168.1.1/internal")

    def test_private_allowed_in_demo(self):
        from app.security.ssrf import validate_external_url

        with patch("app.security.ssrf.settings") as mock_settings:
            mock_settings.app_env.value = "local-demo"
            # Should not raise in local-demo
            result = validate_external_url("http://192.168.1.1/internal", allow_private=True)
            assert result == "http://192.168.1.1/internal"

    def test_blocked_port_22(self):
        from app.security.ssrf import SSRFValidationError, validate_external_url

        with pytest.raises(SSRFValidationError, match="Port 22 is blocked"):
            validate_external_url("http://example.com:22/ssh")

    def test_blocked_port_3306(self):
        from app.security.ssrf import SSRFValidationError, validate_external_url

        with pytest.raises(SSRFValidationError, match="Port 3306 is blocked"):
            validate_external_url("http://example.com:3306/mysql")

    def test_standard_https_port_allowed(self):
        from app.security.ssrf import validate_external_url

        result = validate_external_url("https://example.com:443/secure")
        assert result == "https://example.com:443/secure"


# ---------------------------------------------------------------------------
# Authorization tests
# ---------------------------------------------------------------------------


class TestAuthorization:
    def _make_request(self, user_id="", project_id="", conversation_id="", run_id=""):
        """Create a mock Request with MAA headers."""
        mock = MagicMock()
        mock.state = MagicMock()
        mock.state.maa_user_id = user_id
        mock.state.maa_project_id = project_id
        mock.state.maa_conversation_id = conversation_id
        mock.state.maa_run_id = run_id
        mock.state.trace_id = "trace-1"
        mock.state.request_id = "req-1"
        return mock

    def test_same_user_allowed(self):
        from app.security.authz import verify_conversation_access

        req = self._make_request(user_id="1001")
        # Should not raise
        verify_conversation_access(
            conversation_user_id="1001",
            conversation_project_id="",
            request=req,
        )

    def test_different_user_denied(self):
        from app.security.authz import AuthorizationError, verify_conversation_access

        req = self._make_request(user_id="1001")
        with pytest.raises(AuthorizationError):
            verify_conversation_access(
                conversation_user_id="1002",
                conversation_project_id="",
                request=req,
            )

    def test_empty_headers_skip_check(self):
        """When MAA headers are empty, skip auth check (fallback behavior)."""
        from app.security.authz import verify_conversation_access

        req = self._make_request()
        # Should not raise
        verify_conversation_access(
            conversation_user_id="any-user",
            conversation_project_id="any-project",
            request=req,
        )

    def test_same_project_allowed(self):
        from app.security.authz import verify_conversation_access

        req = self._make_request(project_id="2001")
        verify_conversation_access(
            conversation_user_id="",
            conversation_project_id="2001",
            request=req,
        )

    def test_different_project_denied(self):
        from app.security.authz import AuthorizationError, verify_conversation_access

        req = self._make_request(project_id="2001")
        with pytest.raises(AuthorizationError):
            verify_conversation_access(
                conversation_user_id="",
                conversation_project_id="2002",
                request=req,
            )

    def test_verify_run_access_uses_conversation(self):
        from app.security.authz import AuthorizationError, verify_run_access

        req = self._make_request(user_id="1001")
        with pytest.raises(AuthorizationError):
            verify_run_access(
                run_conversation_id="conv-1",
                request=req,
                conversation_user_id="1002",
                conversation_project_id="",
            )

    def test_get_maa_context(self):
        from app.security.authz import get_maa_context

        req = self._make_request(user_id="1001", project_id="2001", conversation_id="conv-1")
        ctx = get_maa_context(req)
        assert ctx["user_id"] == "1001"
        assert ctx["project_id"] == "2001"
        assert ctx["conversation_id"] == "conv-1"


# ---------------------------------------------------------------------------
# File Upload Validation tests
# ---------------------------------------------------------------------------


class TestFileUploadValidation:
    def test_valid_file_list(self):
        from app.security.upload import validate_input_files

        files = [
            {"url": "https://example.com/image.jpg", "name": "photo.jpg", "type": "image/jpeg", "size": 1024},
            {"url": "https://example.com/video.mp4", "name": "clip.mp4", "type": "video/mp4", "size": 2048},
        ]
        result = validate_input_files(files)
        assert len(result) == 2

    def test_too_many_files_fails(self):
        from app.security.upload import FileUploadError, validate_input_files

        files = [
            {"url": f"https://example.com/file{i}.jpg", "name": f"f{i}.jpg"}
            for i in range(25)
        ]
        with pytest.raises(FileUploadError, match="Too many files"):
            validate_input_files(files)

    def test_file_too_large_fails(self):
        from app.security.upload import FileUploadError, validate_input_files

        files = [
            {"url": "https://example.com/huge.mp4", "name": "huge.mp4", "size": 100 * 1024 * 1024},
        ]
        with pytest.raises(FileUploadError, match="exceeds max size"):
            validate_input_files(files)

    def test_total_size_exceeded_fails(self):
        from app.security.upload import FileUploadError, validate_input_files

        files = [
            {"url": f"https://example.com/file{i}.mp4", "name": f"f{i}.mp4", "size": 20 * 1024 * 1024}
            for i in range(15)  # 15 * 20MB = 300MB > 200MB limit
        ]
        with pytest.raises(FileUploadError, match="Total upload size exceeds limit"):
            validate_input_files(files)

    def test_file_without_extension_fails(self):
        from app.security.upload import FileUploadError, validate_input_files

        files = [
            {"url": "https://example.com/noext", "name": "noext"},
        ]
        with pytest.raises(FileUploadError, match="no recognizable extension"):
            validate_input_files(files)

    def test_empty_list_passes(self):
        from app.security.upload import validate_input_files

        result = validate_input_files([])
        assert result == []

    def test_not_a_list_fails(self):
        from app.security.upload import FileUploadError, validate_input_files

        with pytest.raises(FileUploadError):
            validate_input_files("not a list")


# ---------------------------------------------------------------------------
# Metrics tests
# ---------------------------------------------------------------------------


class TestMetricsCollector:
    def setup_method(self):
        """Reset metrics before each test."""
        from app.observability.metrics import metrics
        metrics.reset()

    def test_record_http_request(self):
        from app.observability.metrics import metrics

        metrics.record_http_request("GET", "/health", 200, 5.0)
        data = metrics.to_dict()
        assert data["http"]["total_requests"] == 1
        assert data["http"]["latency_avg_ms"] == 5.0

    def test_record_llm_tokens(self):
        from app.observability.metrics import metrics

        metrics.record_llm_tokens(150)
        metrics.record_llm_tokens(250)
        data = metrics.to_dict()
        assert data["llm"]["total_tokens"] == 400

    def test_record_tool_execution(self):
        from app.observability.metrics import metrics

        metrics.record_tool_execution("search_materials", True, 120.0)
        metrics.record_tool_execution("render_video", False, 5000.0)
        data = metrics.to_dict()
        assert data["tools"]["total_executions"] == 2
        assert data["tools"]["failures"] == 1
        assert data["tools"]["successes"] == 1

    def test_active_runs(self):
        from app.observability.metrics import metrics

        metrics.set_active_runs(5)
        data = metrics.to_dict()
        assert data["runs"]["active"] == 5

    def test_sse_connections(self):
        from app.observability.metrics import metrics

        metrics.record_sse_connection()
        metrics.record_sse_connection()
        metrics.record_sse_disconnect()
        data = metrics.to_dict()
        assert data["sse"]["total_connections"] == 2
        assert data["sse"]["active_connections"] == 1

    def test_prometheus_export(self):
        from app.observability.metrics import metrics

        metrics.record_http_request("POST", "/conversations", 201, 50.0)
        prom = metrics.to_prometheus()
        assert "# HELP wisecut_agent_http_request_duration_seconds" in prom
        assert "# TYPE wisecut_agent_http_request_duration_seconds histogram" in prom
        assert "wisecut_agent_http_request_duration_seconds_sum" in prom
        assert "wisecut_agent_http_request_duration_seconds_count" in prom
        assert "# TYPE wisecut_agent_http_request_duration_seconds_count" not in prom  # only count, not TYPE

    def test_run_phase_metrics(self):
        from app.observability.metrics import metrics

        metrics.record_run_phase("render", 3000.0)
        data = metrics.to_dict()
        assert "render" in data["runs"]["phases"]
        assert data["runs"]["phases"]["render"]["count"] == 1


# ---------------------------------------------------------------------------
# Rate Limiter tests
# ---------------------------------------------------------------------------


class TestRateLimiter:
    @pytest.mark.asyncio
    async def test_first_request_allowed(self):
        from app.security.rate_limit import RateLimiter

        # Use a unique Redis DB for test isolation
        limiter = RateLimiter(redis_url="redis://localhost:16381/10")
        try:
            allowed, info = await limiter.is_allowed("test-key-a", limit=5, window_seconds=60)
            assert allowed is True
            assert info["remaining"] == 4
        finally:
            await limiter.close()

    @pytest.mark.asyncio
    async def test_exceeding_limit_denied(self):
        from app.security.rate_limit import RateLimiter

        # Use a different unique Redis DB
        limiter = RateLimiter(redis_url="redis://localhost:16381/11")
        try:
            key = "test-key-b"
            for i in range(5):
                allowed, _ = await limiter.is_allowed(key, limit=5, window_seconds=60)
                assert allowed is True
            # 6th request should be denied
            allowed, info = await limiter.is_allowed(key, limit=5, window_seconds=60)
            assert allowed is False
            assert info["remaining"] == 0
        finally:
            await limiter.close()


# ---------------------------------------------------------------------------
# Audit Log Repository tests
# ---------------------------------------------------------------------------


def _make_session():
    session = MagicMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)
    return session


class TestAuditLogRepository:
    async def test_create_audit_log(self):
        from app.persistence.repositories import AuditLogRepository

        session = _make_session()
        session.add = MagicMock()
        session.flush = AsyncMock()
        repo = AuditLogRepository(session)

        log = await repo.create(
            actor_type="user",
            actor_id="user-1001",
            action="approval.decided",
            resource_type="approval",
            resource_id="appr-1",
            payload={"decision": "approved"},
        )
        assert log.actor_type == "user"
        assert log.action == "approval.decided"
        assert log.resource_type == "approval"
        assert log.payload_json == {"decision": "approved"}

    async def test_get_by_resource(self):
        from app.persistence.repositories import AuditLogRepository

        mock_log = MagicMock()
        mock_log.action = "run.started"
        mock_log.resource_type = "run"
        mock_log.resource_id = "run-1"

        session = _make_session()
        session.add = MagicMock()
        session.flush = AsyncMock()
        # Mock the query result
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_log]
        session.execute = AsyncMock(return_value=mock_result)
        repo = AuditLogRepository(session)

        logs = await repo.get_by_resource("run", "run-1")
        assert len(logs) >= 1
        assert logs[0].action == "run.started"
