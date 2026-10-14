"""Tools package: registry, contracts, policy, approval, and executor."""
from app.tools.approval import ApprovalService
from app.tools.contracts import (
    ApprovalRequirement,
    RetryPolicy,
    SecurityLevel,
    ToolContract,
    ToolResult,
)
from app.tools.executor import ToolExecutor
from app.tools.policy import PolicyViolation, ToolPolicy
from app.tools.registry import (
    KNOWN_TOOL_NAMES,
    ToolRegistry,
    get_registry,
    register_default_tools,
)

__all__ = [
    # Contracts
    "SecurityLevel",
    "ApprovalRequirement",
    "RetryPolicy",
    "ToolContract",
    "ToolResult",
    # Registry
    "ToolRegistry",
    "KNOWN_TOOL_NAMES",
    "get_registry",
    "register_default_tools",
    # Policy
    "ToolPolicy",
    "PolicyViolation",
    # Approval
    "ApprovalService",
    # Executor
    "ToolExecutor",
]
