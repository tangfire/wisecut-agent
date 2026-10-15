"""Unit tests for WP-07 Tool and Provider platform."""
from __future__ import annotations

import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


# ---------------------------------------------------------------------------
# Tool Contract tests
# ---------------------------------------------------------------------------


class TestSecurityLevel:
    def test_l0_is_lowest(self):
        from app.tools.contracts import SecurityLevel
        assert SecurityLevel.L0.value == "L0"

    def test_l3_implies_approval(self):
        from app.tools.contracts import SecurityLevel, ToolContract
        contract = ToolContract(
            name="render_video", description="Render",
            input_schema={}, output_schema={}, security_level=SecurityLevel.L3,
        )
        assert contract.requires_approval is True

    def test_l0_does_not_require_approval(self):
        from app.tools.contracts import SecurityLevel, ToolContract
        contract = ToolContract(
            name="normalize", description="Normalize",
            input_schema={}, output_schema={}, security_level=SecurityLevel.L0,
        )
        assert contract.requires_approval is False


class TestRetryPolicy:
    def test_default(self):
        from app.tools.contracts import RetryPolicy
        p = RetryPolicy()
        assert p.max_attempts == 3
        assert p.backoff_factor == 2.0

    def test_custom(self):
        from app.tools.contracts import RetryPolicy
        p = RetryPolicy(max_attempts=5, max_backoff=120.0)
        assert p.max_attempts == 5


# ---------------------------------------------------------------------------
# Tool Registry tests
# ---------------------------------------------------------------------------


class TestToolRegistry:
    def test_register_and_get(self):
        from app.tools.contracts import SecurityLevel, ToolContract
        from app.tools.registry import ToolRegistry
        r = ToolRegistry()
        c = ToolContract(name="t", description="", input_schema={}, output_schema={}, security_level=SecurityLevel.L0)
        r.register(c)
        assert r.get("t") is c

    def test_get_unknown_returns_none(self):
        from app.tools.registry import ToolRegistry
        assert ToolRegistry().get("nonexistent") is None

    def test_get_or_raise(self):
        from app.tools.registry import ToolRegistry
        with pytest.raises(KeyError, match="not registered"):
            ToolRegistry().get_or_raise("nonexistent")

    def test_filter_by_profile(self):
        from app.tools.contracts import SecurityLevel, ToolContract
        from app.tools.registry import ToolRegistry
        r = ToolRegistry()
        r.register(ToolContract(name="safe", description="", input_schema={}, output_schema={}, security_level=SecurityLevel.L0))
        r.register(ToolContract(name="danger", description="", input_schema={}, output_schema={}, security_level=SecurityLevel.L3))
        tools = r.filter_by_profile("q", {SecurityLevel.L0})
        assert len(tools) == 1 and tools[0].name == "safe"

    def test_is_known(self):
        from app.tools.registry import ToolRegistry
        r = ToolRegistry()
        assert r.is_known("read_file") is True
        assert r.is_known("nonexistent") is False


# ---------------------------------------------------------------------------
# Tool Policy tests
# ---------------------------------------------------------------------------


class TestToolPolicy:
    def test_l3_without_approval_raises(self):
        from app.tools.contracts import SecurityLevel, ToolContract
        from app.tools.policy import PolicyViolation, ToolPolicy
        from app.tools.registry import ToolRegistry
        r = ToolRegistry()
        r.register(ToolContract(name="render", description="", input_schema={}, output_schema={}, security_level=SecurityLevel.L3))
        p = ToolPolicy(registry=r)
        with pytest.raises(PolicyViolation, match="requires approval"):
            p.check("render", {})

    def test_l3_with_approved_approval_passes(self):
        from app.tools.contracts import SecurityLevel, ToolContract
        from app.tools.policy import ToolPolicy
        from app.tools.registry import ToolRegistry
        r = ToolRegistry()
        r.register(ToolContract(name="render", description="", input_schema={}, output_schema={}, security_level=SecurityLevel.L3))
        p = ToolPolicy(registry=r)
        approval = MagicMock()
        approval.status = "approved"
        assert p.check("render", {}, approval=approval).name == "render"

    def test_l3_with_pending_approval_raises(self):
        from app.tools.contracts import SecurityLevel, ToolContract
        from app.tools.policy import PolicyViolation, ToolPolicy
        from app.tools.registry import ToolRegistry
        r = ToolRegistry()
        r.register(ToolContract(name="render", description="", input_schema={}, output_schema={}, security_level=SecurityLevel.L3))
        p = ToolPolicy(registry=r)
        approval = MagicMock()
        approval.status = "pending"
        with pytest.raises(PolicyViolation, match="requires approved approval"):
            p.check("render", {}, approval=approval)

    def test_unregistered_tool_raises(self):
        from app.tools.policy import ToolPolicy
        with pytest.raises(KeyError, match="not registered"):
            ToolPolicy().check("nonexistent", {})

    def test_missing_required_input_raises(self):
        from app.tools.contracts import SecurityLevel, ToolContract
        from app.tools.policy import PolicyViolation, ToolPolicy
        from app.tools.registry import ToolRegistry
        r = ToolRegistry()
        r.register(ToolContract(name="needs_url", description="", input_schema={"required": ["url"]}, output_schema={}, security_level=SecurityLevel.L1))
        p = ToolPolicy(registry=r)
        with pytest.raises(PolicyViolation, match="Missing required input"):
            p.check("needs_url", {})

    def test_l0_passes(self):
        from app.tools.contracts import SecurityLevel, ToolContract
        from app.tools.policy import ToolPolicy
        from app.tools.registry import ToolRegistry
        r = ToolRegistry()
        r.register(ToolContract(name="n", description="", input_schema={}, output_schema={}, security_level=SecurityLevel.L0))
        assert ToolPolicy(registry=r).check("n", {}).name == "n"

    def test_security_level_filter(self):
        from app.tools.contracts import SecurityLevel, ToolContract
        from app.tools.policy import PolicyViolation, ToolPolicy
        from app.tools.registry import ToolRegistry
        r = ToolRegistry()
        r.register(ToolContract(name="render", description="", input_schema={}, output_schema={}, security_level=SecurityLevel.L3))
        p = ToolPolicy(registry=r)
        with pytest.raises(PolicyViolation, match="not allowed"):
            p.check("render", {}, allowed_security_levels={SecurityLevel.L0})


# ---------------------------------------------------------------------------
# Approval Service tests
# ---------------------------------------------------------------------------


class TestApprovalService:
    @pytest.mark.asyncio
    async def test_create_approval(self):
        from app.tools import approval as mod
        from app.tools.approval import ApprovalService
        from app.tools.contracts import SecurityLevel, ToolContract
        from app.tools.registry import ToolRegistry

        # Register tool so policy check in _validate_input passes
        r = ToolRegistry()
        r.register(ToolContract(name="render_video", description="", input_schema={}, output_schema={}, security_level=SecurityLevel.L3))

        service = ApprovalService()
        mock_approval = MagicMock()
        mock_approval.id = "appr-1"
        mock_approval.status.value = "pending"
        mock_approval.conversation_id = "conv-1"
        mock_approval.run_id = "run-1"
        mock_approval.tool_name = "render_video"
        mock_approval.arguments_json = {}
        mock_approval.decision_json = None
        mock_approval.expires_at = None
        mock_approval.created_at.isoformat.return_value = "2024-01-01T00:00:00"
        mock_approval.resolved_at = None

        mock_session = AsyncMock()
        mock_a_repo = AsyncMock()
        mock_a_repo.create = AsyncMock(return_value=mock_approval)
        mock_e_repo = AsyncMock()
        mock_e_repo.get_next_seq = AsyncMock(return_value=1)
        mock_o_repo = AsyncMock()

        mock_uow_inst = MagicMock()
        mock_uow_inst.session = mock_session
        mock_uow_inst.__aenter__ = AsyncMock(return_value=mock_uow_inst)
        mock_uow_inst.__aexit__ = AsyncMock(return_value=False)

        with patch.object(mod, "ApprovalRepository", MagicMock(return_value=mock_a_repo)), \
             patch.object(mod, "EventRepository", MagicMock(return_value=mock_e_repo)), \
             patch.object(mod, "OutboxRepository", MagicMock(return_value=mock_o_repo)), \
             patch.object(mod, "unit_of_work") as mock_uow:
            mock_uow.return_value = mock_uow_inst
            result = await service.create(conversation_id="conv-1", run_id="run-1", tool_name="render_video", arguments={})

        assert result["id"].startswith("approval-")
        assert result["status"] == "pending"

    @pytest.mark.asyncio
    async def test_decide_approval(self):
        from app.persistence.models import ApprovalStatus
        from app.tools import approval as mod
        from app.tools.approval import ApprovalService
        from app.tools.contracts import SecurityLevel, ToolContract
        from app.tools.registry import ToolRegistry

        r = ToolRegistry()
        r.register(ToolContract(name="render_video", description="", input_schema={}, output_schema={}, security_level=SecurityLevel.L3))

        service = ApprovalService()
        mock_approval = MagicMock()
        mock_approval.id = "appr-1"
        mock_approval.status = ApprovalStatus.PENDING
        mock_approval.conversation_id = "conv-1"
        mock_approval.run_id = "run-1"
        mock_approval.tool_name = "render_video"
        mock_approval.decision_json = None
        mock_approval.resolved_at = None
        mock_approval.created_at.isoformat.return_value = "2024-01-01T00:00:00"

        mock_session = AsyncMock()
        mock_a_repo = AsyncMock()
        mock_a_repo.get_by_id = AsyncMock(return_value=mock_approval)
        mock_a_repo.decide = AsyncMock()
        mock_e_repo = AsyncMock()
        mock_e_repo.get_next_seq = AsyncMock(return_value=1)
        mock_o_repo = AsyncMock()

        mock_uow_inst = MagicMock()
        mock_uow_inst.session = mock_session
        mock_uow_inst.__aenter__ = AsyncMock(return_value=mock_uow_inst)
        mock_uow_inst.__aexit__ = AsyncMock(return_value=False)

        with patch.object(mod, "ApprovalRepository", MagicMock(return_value=mock_a_repo)), \
             patch.object(mod, "EventRepository", MagicMock(return_value=mock_e_repo)), \
             patch.object(mod, "OutboxRepository", MagicMock(return_value=mock_o_repo)), \
             patch.object(mod, "unit_of_work") as mock_uow:
            mock_uow.return_value = mock_uow_inst
            result = await service.decide(approval_id="appr-1", decision_type="approve")

        assert result["should_resume_runner"] is True
        assert result["approval"]["status"] == "approved"

    @pytest.mark.asyncio
    async def test_decide_unknown_raises(self):
        from app.tools import approval as mod
        from app.tools.approval import ApprovalService
        from app.tools.contracts import SecurityLevel, ToolContract
        from app.tools.registry import ToolRegistry

        r = ToolRegistry()
        r.register(ToolContract(name="render_video", description="", input_schema={}, output_schema={}, security_level=SecurityLevel.L3))
        service = ApprovalService()

        mock_session = AsyncMock()
        mock_a_repo = AsyncMock()
        mock_a_repo.get_by_id = AsyncMock(return_value=None)

        mock_uow_inst = MagicMock()
        mock_uow_inst.session = mock_session
        mock_uow_inst.__aenter__ = AsyncMock(return_value=mock_uow_inst)
        mock_uow_inst.__aexit__ = AsyncMock(return_value=False)

        with patch.object(mod, "ApprovalRepository", MagicMock(return_value=mock_a_repo)), \
             patch.object(mod, "EventRepository"), \
             patch.object(mod, "OutboxRepository"), \
             patch.object(mod, "unit_of_work") as mock_uow:
            mock_uow.return_value = mock_uow_inst
            with pytest.raises(ValueError, match="not found"):
                await service.decide("unknown", "approve")

    @pytest.mark.asyncio
    async def test_get_approval(self):
        from app.tools import approval as mod
        from app.tools.approval import ApprovalService

        service = ApprovalService()
        mock_approval = MagicMock()
        mock_approval.id = "appr-1"
        mock_approval.status.value = "pending"
        mock_approval.conversation_id = "conv-1"
        mock_approval.run_id = "run-1"
        mock_approval.tool_name = "render_video"
        mock_approval.arguments_json = {}
        mock_approval.decision_json = None
        mock_approval.expires_at = None
        mock_approval.created_at.isoformat.return_value = "2024-01-01T00:00:00"
        mock_approval.resolved_at = None

        mock_session = AsyncMock()
        mock_a_repo = AsyncMock()
        mock_a_repo.get_by_id = AsyncMock(return_value=mock_approval)

        mock_uow_inst = MagicMock()
        mock_uow_inst.session = mock_session
        mock_uow_inst.__aenter__ = AsyncMock(return_value=mock_uow_inst)
        mock_uow_inst.__aexit__ = AsyncMock(return_value=False)

        with patch.object(mod, "ApprovalRepository", MagicMock(return_value=mock_a_repo)), \
             patch.object(mod, "unit_of_work") as mock_uow:
            mock_uow.return_value = mock_uow_inst
            result = await service.get("appr-1")

        assert result is not None
        assert result["id"] == "appr-1"

    @pytest.mark.asyncio
    async def test_get_unknown_returns_none(self):
        from app.tools import approval as mod
        from app.tools.approval import ApprovalService

        service = ApprovalService()
        mock_session = AsyncMock()
        mock_a_repo = AsyncMock()
        mock_a_repo.get_by_id = AsyncMock(return_value=None)

        mock_uow_inst = MagicMock()
        mock_uow_inst.session = mock_session
        mock_uow_inst.__aenter__ = AsyncMock(return_value=mock_uow_inst)
        mock_uow_inst.__aexit__ = AsyncMock(return_value=False)

        with patch.object(mod, "ApprovalRepository", MagicMock(return_value=mock_a_repo)), \
             patch.object(mod, "unit_of_work") as mock_uow:
            mock_uow.return_value = mock_uow_inst
            result = await service.get("unknown")
        assert result is None


# ---------------------------------------------------------------------------
# Tool Executor tests
# ---------------------------------------------------------------------------


class TestToolExecutor:
    @pytest.mark.asyncio
    async def test_execute_success(self):
        from app.tools.contracts import SecurityLevel, ToolContract
        from app.tools.executor import ToolExecutor
        from app.tools.registry import ToolRegistry

        r = ToolRegistry()
        r.register(ToolContract(name="t", description="", input_schema={}, output_schema={}, security_level=SecurityLevel.L0))
        executor = ToolExecutor(registry=r)

        async def ok_func(input_data):
            return {"result": "ok"}

        mock_tool_repo = AsyncMock()
        mock_tool_repo.create = AsyncMock(return_value=MagicMock(id="tool-1"))
        mock_event_repo = AsyncMock()
        mock_event_repo.get_next_seq = AsyncMock(return_value=1)
        mock_outbox_repo = AsyncMock()
        mock_session = AsyncMock()

        mock_uow_inst = MagicMock()
        mock_uow_inst.session = mock_session
        mock_uow_inst.__aenter__ = AsyncMock(return_value=mock_uow_inst)
        mock_uow_inst.__aexit__ = AsyncMock(return_value=False)

        with patch("app.persistence.repositories.ToolExecutionRepository", MagicMock(return_value=mock_tool_repo)), \
             patch("app.persistence.repositories.EventRepository", MagicMock(return_value=mock_event_repo)), \
             patch("app.persistence.repositories.OutboxRepository", MagicMock(return_value=mock_outbox_repo)), \
             patch("app.tools.executor.unit_of_work") as mock_uow:
            mock_uow.return_value = mock_uow_inst
            result = await executor.execute(
                tool_name="t", conversation_id="c", run_id="r",
                input_data={}, tool_func=ok_func,
            )

        assert result.status == "success"
        assert result.output == {"result": "ok"}

    @pytest.mark.asyncio
    async def test_execute_unregistered_fails(self):
        from app.tools.executor import ToolExecutor
        from app.tools.registry import ToolRegistry
        r = ToolRegistry()  # empty
        executor = ToolExecutor(registry=r)
        result = await executor.execute(
            tool_name="nonexistent", conversation_id="c", run_id="r",
            input_data={}, tool_func=AsyncMock(return_value={}),
        )
        assert result.status == "failed"
        assert "not registered" in (result.error or "")

    @pytest.mark.asyncio
    async def test_execute_l3_without_approval_fails(self):
        from app.tools.contracts import SecurityLevel, ToolContract
        from app.tools.executor import ToolExecutor
        from app.tools.registry import ToolRegistry
        r = ToolRegistry()
        r.register(ToolContract(name="render", description="", input_schema={}, output_schema={}, security_level=SecurityLevel.L3))
        executor = ToolExecutor(registry=r)
        result = await executor.execute(
            tool_name="render", conversation_id="c", run_id="r",
            input_data={}, tool_func=AsyncMock(return_value={}),
        )
        assert result.status == "failed"
        assert result.error_code == "policy_violation"

    @pytest.mark.asyncio
    async def test_execute_retries_on_failure(self):
        from app.tools.contracts import RetryPolicy, SecurityLevel, ToolContract
        from app.tools.executor import ToolExecutor
        from app.tools.registry import ToolRegistry

        r = ToolRegistry()
        r.register(ToolContract(
            name="flaky", description="",
            input_schema={}, output_schema={}, security_level=SecurityLevel.L0,
            retry_policy=RetryPolicy(max_attempts=2, backoff_base=0.01),
        ))
        executor = ToolExecutor(registry=r)

        call_count = 0
        async def flaky(input_data):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise RuntimeError("transient")
            return {"ok": True}

        mock_tool_repo = AsyncMock()
        mock_tool_repo.create = AsyncMock(return_value=MagicMock(id="t1"))
        mock_tool_repo.mark_completed = AsyncMock()
        mock_tool_repo.mark_failed = AsyncMock()
        mock_event_repo = AsyncMock()
        mock_event_repo.get_next_seq = AsyncMock(return_value=1)
        mock_outbox_repo = AsyncMock()
        mock_session = AsyncMock()

        mock_uow_inst = MagicMock()
        mock_uow_inst.session = mock_session
        mock_uow_inst.__aenter__ = AsyncMock(return_value=mock_uow_inst)
        mock_uow_inst.__aexit__ = AsyncMock(return_value=False)

        with patch("app.persistence.repositories.ToolExecutionRepository", MagicMock(return_value=mock_tool_repo)), \
             patch("app.persistence.repositories.EventRepository", MagicMock(return_value=mock_event_repo)), \
             patch("app.persistence.repositories.OutboxRepository", MagicMock(return_value=mock_outbox_repo)), \
             patch("app.tools.executor.unit_of_work") as mock_uow:
            mock_uow.return_value = mock_uow_inst
            result = await executor.execute(
                tool_name="flaky", conversation_id="c", run_id="r",
                input_data={}, tool_func=flaky,
            )

        assert result.status == "success"
        assert call_count == 2
