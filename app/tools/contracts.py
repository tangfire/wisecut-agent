"""Tool contracts and security levels for Agent Film.

Security levels (plan.md §8.4):
  L0: Pure functions / local format conversion, no external side effects
  L1: Read-only HTTP / material queries, requires SSRF protection
  L2: Creates external tasks or uploads files, requires timeout, idempotency, and approval
  L3: Billing, publishing, deletion, or business data mutation — MUST require human approval and audit
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SecurityLevel(str, Enum):
    """Tool risk classification."""

    L0 = "L0"  # Pure function, no external side effects
    L1 = "L1"  # Read-only HTTP / query
    L2 = "L2"  # Creates external tasks, needs approval (ask)
    L3 = "L3"  # Billing / publish / delete, requires approval (require)


class ApprovalRequirement(str, Enum):
    """Whether a tool requires approval before execution."""

    NONE = "none"      # No approval needed
    ASK = "ask"        # Ask user (L2)
    REQUIRE = "require"  # Must have approval (L3)


@dataclass(frozen=True)
class RetryPolicy:
    """Retry configuration for a tool."""

    max_attempts: int = 3
    backoff_base: float = 1.0
    backoff_factor: float = 2.0
    max_backoff: float = 60.0

    # Which exceptions trigger a retry
    retryable_errors: tuple[str, ...] = (
        "timeout",
        "rate_limit",
        "provider_unavailable",
        "network_error",
    )


@dataclass(frozen=True)
class ToolContract:
    """Immutable contract for a tool.

    Aligns with frontend tool_name union:
      read_file, write_todos, strategy_reference_agent,
      material_package_curator_agent, read_artifact,
      creative_rhythm_agent, content_production_agent,
      post_production_agent, build_final_delivery_from_artifacts
    """

    name: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    security_level: SecurityLevel = SecurityLevel.L0
    approval_requirement: ApprovalRequirement = ApprovalRequirement.NONE
    timeout_seconds: int = 30
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    provider: str = "unknown"
    requires_approval: bool = False

    def __post_init__(self) -> None:
        # Derive requires_approval from security level if not explicitly set
        if self.security_level in (SecurityLevel.L2, SecurityLevel.L3):
            object.__setattr__(self, "requires_approval", True)


@dataclass
class ToolResult:
    """Result of a tool execution."""

    tool_name: str
    status: str  # "success" | "failed" | "timeout" | "cancelled"
    output: dict[str, Any] | None = None
    error: str | None = None
    error_code: str | None = None
    attempt: int = 1
    duration_ms: float = 0.0
