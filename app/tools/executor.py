"""Tool Executor: the complete execution pipeline for tools.

Pipeline:
  Policy Check → Input Validation → Approval Check →
  tool.started → Provider Execution → Output Validation →
  tool.completed / tool.failed

Usage:
    executor = ToolExecutor()
    result = await executor.execute(
        tool_name="render_video",
        conversation_id="conv-1",
        run_id="run-1",
        input_data={"aspect_ratio": "16:9"},
        approval=approval_record,  # Required for L3
    )
"""
from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Coroutine
from typing import Any

from app.persistence.unit_of_work import unit_of_work
from app.tools.contracts import SecurityLevel, ToolResult
from app.tools.policy import PolicyViolation, ToolPolicy
from app.tools.registry import get_registry

logger = logging.getLogger(__name__)

# Type for the actual tool implementation function
ToolFunc = Coroutine[Any, Any, dict[str, Any]]


class ToolExecutor:
    """Executes tools through the full policy → provider → event pipeline.

    WP-08/WP-09 provide the actual provider implementations.
    This class handles the cross-cutting concerns: policy, events, recording.

    Usage:
        executor = ToolExecutor()
        result = await executor.execute(
            tool_name="render_video",
            conversation_id="conv-1",
            run_id="run-1",
            input_data={"aspect_ratio": "16:9"},
            tool_func=my_tool_func,
            approval=approval_record,
        )

    For testing with a custom registry:
        executor = ToolExecutor(registry=my_registry)
    """

    def __init__(self, registry: ToolRegistry | None = None) -> None:
        self._registry = registry or get_registry()
        self._policy = ToolPolicy(registry=self._registry)

    async def execute(
        self,
        tool_name: str,
        conversation_id: str,
        run_id: str,
        input_data: dict[str, Any],
        tool_func: ToolFunc,
        approval: Any | None = None,
        allowed_security_levels: set[SecurityLevel] | None = None,
    ) -> ToolResult:
        """Execute a tool through the full pipeline.

        Args:
            tool_name: Name of the tool to execute.
            conversation_id: The conversation ID.
            run_id: The run ID.
            input_data: Input parameters.
            tool_func: Async function that performs the actual work.
                       Must accept (input_data, **context) and return a dict.
            approval: Approval record if the tool requires approval.
            allowed_security_levels: Security levels allowed in this context.

        Returns:
            ToolResult with status, output, and timing.
        """
        contract = self._registry.get(tool_name)
        if contract is None:
            return ToolResult(
                tool_name=tool_name,
                status="failed",
                error=f"Tool {tool_name!r} not registered",
                error_code="tool_not_found",
            )

        # 1. Policy check
        try:
            self._policy.check(
                tool_name=tool_name,
                input_data=input_data,
                approval=approval,
                allowed_security_levels=allowed_security_levels,
            )
        except PolicyViolation as exc:
            logger.warning("Policy blocked tool: %s", exc)
            return ToolResult(
                tool_name=tool_name,
                status="failed",
                error=str(exc),
                error_code="policy_violation",
            )

        # 2. Create tool_execution record
        tool_execution_id = await self._create_tool_execution(
            conversation_id=conversation_id,
            run_id=run_id,
            tool_name=tool_name,
            input_data=input_data,
        )

        # 3. Emit tool.started
        await self._emit_tool_event(
            conversation_id=conversation_id,
            run_id=run_id,
            event_type="tool.started",
            tool_name=tool_name,
            tool_execution_id=tool_execution_id,
            payload={"input": input_data},
        )

        # 4. Execute with retry
        start_time = time.monotonic()
        result = await self._execute_with_retry(
            tool_func=tool_func,
            input_data=input_data,
            retry_policy=contract.retry_policy,
        )
        duration_ms = (time.monotonic() - start_time) * 1000

        # 5. Emit tool.completed or tool.failed
        if result.status == "success":
            await self._emit_tool_event(
                conversation_id=conversation_id,
                run_id=run_id,
                event_type="tool.completed",
                tool_name=tool_name,
                tool_execution_id=tool_execution_id,
                payload={"output": result.output},
            )
        else:
            await self._emit_tool_event(
                conversation_id=conversation_id,
                run_id=run_id,
                event_type="tool.failed",
                tool_name=tool_name,
                tool_execution_id=tool_execution_id,
                payload={"error": result.error, "error_code": result.error_code},
            )

        # 6. Update tool_execution record
        await self._update_tool_execution(
            tool_execution_id=tool_execution_id,
            result=result,
            duration_ms=duration_ms,
        )

        logger.info(
            "Tool %s completed: status=%s duration=%.0fms attempt=%d",
            tool_name,
            result.status,
            duration_ms,
            result.attempt,
        )

        return result

    async def _execute_with_retry(
        self,
        tool_func: ToolFunc,
        input_data: dict[str, Any],
        retry_policy: Any,
        max_attempts: int = 3,
    ) -> ToolResult:
        """Execute a tool with retry logic."""
        attempt = 0
        last_error: str | None = None
        last_error_code: str | None = None

        while attempt < max_attempts:
            attempt += 1
            try:
                output = await asyncio.wait_for(
                    tool_func(input_data),
                    timeout=30.0,  # Default timeout; contract has its own
                )
                return ToolResult(
                    tool_name="",
                    status="success",
                    output=output,
                    attempt=attempt,
                )
            except TimeoutError:
                last_error = "Tool execution timed out"
                last_error_code = "timeout"
                logger.warning("Tool attempt %d timed out", attempt)
            except Exception as exc:
                last_error = str(exc)
                last_error_code = getattr(exc, "error_code", "execution_error")
                logger.warning("Tool attempt %d failed: %s", attempt, exc)

            if attempt < max_attempts:
                # Exponential backoff
                backoff = min(
                    retry_policy.backoff_base * (retry_policy.backoff_factor ** (attempt - 1)),
                    retry_policy.max_backoff,
                )
                await asyncio.sleep(backoff)

        return ToolResult(
            tool_name="",
            status="failed",
            error=last_error,
            error_code=last_error_code,
            attempt=attempt,
        )

    async def _create_tool_execution(
        self,
        conversation_id: str,
        run_id: str,
        tool_name: str,
        input_data: dict[str, Any],
    ) -> str:
        """Create a ToolExecution record."""
        from app.persistence.repositories import ToolExecutionRepository
        from app.protocol.language import generate_id

        tool_execution_id = generate_id("tool")
        async with unit_of_work() as uow:
            repo = ToolExecutionRepository(uow.session)
            await repo.create(
                tool_execution_id=tool_execution_id,
                conversation_id=conversation_id,
                run_id=run_id,
                tool_name=tool_name,
                input_data=input_data,
            )
        return tool_execution_id

    async def _update_tool_execution(
        self,
        tool_execution_id: str,
        result: ToolResult,
        duration_ms: float,
    ) -> None:
        """Update ToolExecution record with result."""
        from app.persistence.repositories import ToolExecutionRepository

        async with unit_of_work() as uow:
            repo = ToolExecutionRepository(uow.session)
            if result.status == "success":
                await repo.mark_completed(
                    tool_execution_id=tool_execution_id,
                    output=result.output or {},
                )
            else:
                await repo.mark_failed(
                    tool_execution_id=tool_execution_id,
                    error=result.error or "Unknown error",
                    error_code=result.error_code,
                )

    async def _emit_tool_event(
        self,
        conversation_id: str,
        run_id: str,
        event_type: str,
        tool_name: str,
        tool_execution_id: str,
        payload: dict[str, Any],
    ) -> None:
        """Emit a tool event (tool.started / tool.completed / tool.failed)."""
        from app.persistence.repositories import EventRepository, OutboxRepository
        from app.protocol.language import generate_id

        event_id = generate_id("event")
        async with unit_of_work() as uow:
            event_repo = EventRepository(uow.session)
            outbox_repo = OutboxRepository(uow.session)

            seq = await event_repo.get_next_seq(conversation_id, run_id)
            payload_with_meta = {
                **payload,
                "tool_call_id": tool_execution_id,
                "tool_name": tool_name,
            }
            await event_repo.create(
                event_id=event_id,
                conversation_id=conversation_id,
                run_id=run_id,
                seq=seq,
                event_type=event_type,
                payload=payload_with_meta,
            )
            await outbox_repo.enqueue(
                aggregate_type="tool",
                aggregate_id=tool_execution_id,
                event_type=event_type,
                payload=payload_with_meta,
            )
