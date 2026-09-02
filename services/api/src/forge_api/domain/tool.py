"""Tool domain model for the FP8 Agentic Development Engine.

Provider-neutral records, enums, and protocols for agent tool execution.
Provider SDKs, concrete subprocess executors, or presentation types
must NEVER appear in this module.
"""
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable
from uuid import UUID


class ToolCategory(StrEnum):
    """Categorization of agent development tools."""

    REPOSITORY = "repository"
    CODE = "code"
    FILE = "file"
    GIT = "git"
    TERMINAL = "terminal"
    MEMORY = "memory"


class RiskLevel(StrEnum):
    """Risk classification for tool execution and approval policies."""

    READ_ONLY = "read_only"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True, slots=True)
class ToolExecutionContext:
    """Execution context provided to a tool when invoked by the agent orchestrator."""

    workspace_id: UUID
    repository_id: UUID | None
    user_id: UUID
    session_id: UUID
    repo_root: str | None = None
    timeout_seconds: float = 30.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ToolResult:
    """Standardized outcome of a tool execution."""

    success: bool
    output: str
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class Tool(Protocol):
    """Provider-agnostic port for an agent tool."""

    @property
    def name(self) -> str:
        """Unique identifier of the tool (e.g. 'repository.read_file')."""
        ...

    @property
    def description(self) -> str:
        """Human and LLM readable explanation of what the tool does."""
        ...

    @property
    def category(self) -> ToolCategory:
        """Domain category."""
        ...

    @property
    def risk_level(self) -> RiskLevel:
        """Risk classification governing approval requirements."""
        ...

    @property
    def input_schema(self) -> dict[str, Any]:
        """JSON Schema defining valid input parameters."""
        ...

    @property
    def output_schema(self) -> dict[str, Any]:
        """JSON Schema defining output payload structure."""
        ...

    @property
    def enabled(self) -> bool:
        """Whether this tool is currently available for execution."""
        ...

    def validate(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Validate raw input arguments against tool schema."""
        ...

    async def execute(
        self, context: ToolExecutionContext, input_data: dict[str, Any]
    ) -> ToolResult:
        """Execute the tool within the provided execution boundary."""
        ...
