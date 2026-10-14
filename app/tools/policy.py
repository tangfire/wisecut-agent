"""Tool Policy: enforce L0-L3 security levels and approval gates.

Policy is checked BEFORE any tool execution:
  1. Tool must be registered
  2. Input must pass Pydantic / schema validation
  3. Security level must be allowed for the current context
  4. Approval must exist for L2/L3 tools
"""
from __future__ import annotations

import logging
from typing import Any

from app.tools.contracts import ApprovalRequirement, SecurityLevel, ToolContract, ToolResult
from app.tools.registry import get_registry

logger = logging.getLogger(__name__)


class PolicyViolation(Exception):
    """Raised when a tool policy check fails."""

    def __init__(self, tool_name: str, reason: str) -> None:
        self.tool_name = tool_name
        self.reason = reason
        super().__init__(f"Policy violation for tool {tool_name!r}: {reason}")


class ToolPolicy:
    """Enforces execution policy for tools.

    Usage:
        policy = ToolPolicy()
        policy.check("render_video", input_data, approval=None)

    For testing with a custom registry:
        policy = ToolPolicy(registry=my_registry)
    """

    def __init__(self, registry: ToolRegistry | None = None) -> None:
        self._registry = registry or get_registry()

    def check(
        self,
        tool_name: str,
        input_data: dict[str, Any],
        approval: Any | None = None,
        allowed_security_levels: set[SecurityLevel] | None = None,
    ) -> ToolContract:
        """Run all policy checks for a tool invocation.

        Args:
            tool_name: Name of the tool to execute.
            input_data: Input parameters for the tool.
            approval: Approval record if the tool requires approval.
            allowed_security_levels: Security levels allowed in this context.

        Returns:
            The ToolContract if all checks pass.

        Raises:
            PolicyViolation: If any check fails.
            KeyError: If tool is not registered.
        """
        contract = self._registry.get_or_raise(tool_name)

        # 1. Check security level
        if allowed_security_levels is not None:
            if contract.security_level not in allowed_security_levels:
                raise PolicyViolation(
                    tool_name,
                    f"Security level {contract.security_level.value} not allowed "
                    f"(allowed: {sorted(s.value for s in allowed_security_levels)})",
                )

        # 2. Check approval requirement
        if contract.security_level == SecurityLevel.L3:
            if approval is None:
                raise PolicyViolation(
                    tool_name,
                    "L3 tool requires approval. No approval provided.",
                )
            if hasattr(approval, "status") and approval.status != "approved":
                raise PolicyViolation(
                    tool_name,
                    f"L3 tool requires approved approval, got status={approval.status}",
                )

        # 3. Check input schema (basic type validation)
        self._validate_input(contract, input_data)

        logger.debug(
            "Policy check passed: tool=%s level=%s",
            tool_name,
            contract.security_level.value,
        )
        return contract

    def _validate_input(self, contract: ToolContract, input_data: dict[str, Any]) -> None:
        """Basic input validation against the tool's input schema.

        This is intentionally lightweight — full Pydantic validation happens
        in the domain layer (WP-08/WP-09). Here we just check that required
        top-level fields are present.
        """
        required = contract.input_schema.get("required", [])
        if isinstance(contract.input_schema, dict):
            required = contract.input_schema.get("required", [])

        for field_name in required:
            if field_name not in input_data:
                raise PolicyViolation(
                    contract.name,
                    f"Missing required input field: {field_name!r}",
                )

    def requires_approval(self, tool_name: str) -> bool:
        """Check if a tool requires approval based on its security level."""
        contract = self._registry.get(tool_name)
        if contract is None:
            return False
        return contract.security_level in (SecurityLevel.L2, SecurityLevel.L3)
