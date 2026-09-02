"""Agent domain model and state machine rules for the FP8 Agentic Development Engine.

Contains domain records, statuses, execution limits, and strict state transition rules.
Provider SDKs, SQLAlchemy models, and presentation types must NEVER appear here.
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from forge_api.domain.errors import DomainError
from forge_api.domain.tool import RiskLevel

# ─── Enums ────────────────────────────────────────────────────────────


class AgentStatus(StrEnum):
    """Lifecycle states of an agent execution session."""

    CREATED = "created"
    PLANNING = "planning"
    RUNNING = "running"
    WAITING_FOR_APPROVAL = "waiting_for_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"
    EXPIRED = "expired"


class StepStatus(StrEnum):
    """Lifecycle states of an individual plan step."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class ToolCallStatus(StrEnum):
    """Lifecycle states of an individual tool call."""

    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ─── State Machine Rules ──────────────────────────────────────────────

TERMINAL_AGENT_STATUSES: frozenset[AgentStatus] = frozenset({
    AgentStatus.COMPLETED,
    AgentStatus.FAILED,
    AgentStatus.CANCELLED,
    AgentStatus.TIMED_OUT,
    AgentStatus.EXPIRED,
})

VALID_AGENT_STATUS_TRANSITIONS: dict[AgentStatus, frozenset[AgentStatus]] = {
    AgentStatus.CREATED: frozenset({
        AgentStatus.PLANNING,
        AgentStatus.CANCELLED,
    }),
    AgentStatus.PLANNING: frozenset({
        AgentStatus.RUNNING,
        AgentStatus.FAILED,
        AgentStatus.CANCELLED,
    }),
    AgentStatus.RUNNING: frozenset({
        AgentStatus.WAITING_FOR_APPROVAL,
        AgentStatus.COMPLETED,
        AgentStatus.FAILED,
        AgentStatus.CANCELLED,
        AgentStatus.TIMED_OUT,
    }),
    AgentStatus.WAITING_FOR_APPROVAL: frozenset({
        AgentStatus.RUNNING,
        AgentStatus.CANCELLED,
        AgentStatus.TIMED_OUT,
        AgentStatus.EXPIRED,
    }),
    AgentStatus.COMPLETED: frozenset(),
    AgentStatus.FAILED: frozenset(),
    AgentStatus.CANCELLED: frozenset(),
    AgentStatus.TIMED_OUT: frozenset(),
    AgentStatus.EXPIRED: frozenset(),
}


def is_terminal_agent_status(status: AgentStatus) -> bool:
    """Return True if the status represents an immutable terminal state."""
    return status in TERMINAL_AGENT_STATUSES


def is_valid_agent_transition(current: AgentStatus, target: AgentStatus) -> bool:
    """Check if the transition from current to target status is permitted."""
    allowed = VALID_AGENT_STATUS_TRANSITIONS.get(current, frozenset())
    return target in allowed


def validate_agent_transition(current: AgentStatus, target: AgentStatus) -> None:
    """Validate transition or raise DomainError if not allowed."""
    if not is_valid_agent_transition(current, target):
        raise DomainError(
            f"Invalid agent status transition from '{current.value}' to '{target.value}'.",
            code="invalid_state_transition",
        )


# ─── Limits & Telemetry Records ───────────────────────────────────────


@dataclass(frozen=True, slots=True)
class AgentLimits:
    """Global execution boundaries for an agent session."""

    max_wall_time_seconds: int = 900
    max_llm_calls: int = 30
    max_tool_calls: int = 50
    max_output_bytes: int = 65_536
    max_observation_bytes: int = 8_192


@dataclass(frozen=True, slots=True)
class ExecutionMetrics:
    """Cumulative operational metrics for an agent session."""

    total_llm_calls: int = 0
    total_tool_calls: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    wall_time_seconds: float = 0.0
    estimated_cost_usd: float = 0.0


# ─── Domain Records ───────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class AgentSessionRecord:
    """Top-level agent execution session."""

    id: UUID
    workspace_id: UUID
    user_id: UUID
    objective: str
    status: AgentStatus
    created_at: datetime
    repository_id: UUID | None = None
    conversation_id: UUID | None = None
    model: str | None = None
    limits: AgentLimits = field(default_factory=AgentLimits)
    metrics: ExecutionMetrics = field(default_factory=ExecutionMetrics)
    current_step: int = 0
    started_at: datetime | None = None
    completed_at: datetime | None = None
    cancelled_at: datetime | None = None
    deleted_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AgentStepRecord:
    """A discrete step in an agent plan."""

    id: UUID
    session_id: UUID
    sequence: int
    objective: str
    status: StepStatus
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AgentToolCallRecord:
    """An individual tool execution proposed or completed within a session."""

    id: UUID
    session_id: UUID
    tool_name: str
    arguments: dict[str, Any]
    risk_level: RiskLevel
    status: ToolCallStatus
    created_at: datetime
    step_id: UUID | None = None
    approval_id: UUID | None = None
    output: str | None = None
    error_message: str | None = None
    duration_ms: float | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
