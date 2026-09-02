"""Tool domain model for the FP8 Agentic Development Engine.

Provider-neutral records, enums, protocols, path security, and secret
redaction for agent tool execution. Provider SDKs, concrete subprocess
executors, or presentation types must NEVER appear in this module.
"""
import re
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol, runtime_checkable
from uuid import UUID

from forge_api.domain.errors import ValidationError


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


# ─── Path Containment & Security ──────────────────────────────────────


def safe_resolve_repo_path(
    repo_root: str | Path, relative_path: str | Path
) -> Path:
    """Validate and resolve a path to ensure it remains strictly inside repository root.

    Rejects:
    - Empty paths or paths containing null bytes
    - Absolute paths (Unix or Windows drive paths, e.g. /etc, C:\\..., \\\\...)
    - Traversal components ('..')
    - Paths attempting to access or modify .git or .git/ internals
    - Symlinks that resolve outside the repository root
    - Paths resolving outside the canonical repository root

    Returns the resolved Path object. Raises ValidationError if validation fails.
    """
    if not repo_root:
        raise ValidationError(
            "Repository root must not be empty.", code="invalid_repo_root"
        )

    resolved_root = Path(repo_root).resolve()

    if not relative_path:
        raise ValidationError("Path must not be empty.", code="invalid_path")

    raw_str = str(relative_path).strip()
    if not raw_str or "\0" in raw_str:
        raise ValidationError(
            "Path must not be empty or contain null bytes.", code="invalid_path"
        )

    # Reject absolute paths (Path.is_absolute(), leading slashes, Windows drive letters)
    path_obj = Path(raw_str)
    if (
        path_obj.is_absolute()
        or raw_str.startswith(("/", "\\"))
        or bool(re.match(r"^[a-zA-Z]:", raw_str))
    ):
        raise ValidationError(
            f"Absolute path '{raw_str}' is not permitted.",
            code="path_traversal",
        )

    # Normalize separators for traversal check
    normalized_parts = raw_str.replace("\\", "/").split("/")
    if ".." in normalized_parts:
        raise ValidationError(
            f"Path traversal '..' in '{raw_str}' is not permitted.",
            code="path_traversal",
        )

    # Forbid .git access
    clean_parts = [p for p in normalized_parts if p and p != "."]
    if any(part.lower() == ".git" for part in clean_parts):
        raise ValidationError(
            f"Access to .git directory in '{raw_str}' is forbidden.",
            code="forbidden_path",
        )

    # Combine and resolve
    target_path = (resolved_root / path_obj).resolve()

    # Check containment relative to root
    try:
        target_path.relative_to(resolved_root)
    except ValueError:
        raise ValidationError(
            f"Path '{raw_str}' resolves outside repository root.",
            code="path_traversal",
        ) from None

    # Check existing symlinks in the path hierarchy
    curr = target_path
    while curr != resolved_root and curr.parent != curr:
        if curr.is_symlink():
            try:
                curr.resolve().relative_to(resolved_root)
            except ValueError:
                raise ValidationError(
                    f"Symlink '{curr.name}' resolves outside repository root.",
                    code="symlink_escape",
                ) from None
        curr = curr.parent

    return target_path


# ─── Secret Sanitization ──────────────────────────────────────────────

_SECRET_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # Bearer tokens
    (
        re.compile(
            r"(Bearer\s+)[A-Za-z0-9\-_=]+\.[A-Za-z0-9\-_=]+\.?[A-Za-z0-9\-_.+/=]*",
            re.IGNORECASE,
        ),
        r"\1[REDACTED_TOKEN]",
    ),
    # Common API key formats (sk-..., ghp_..., github_pat_...)
    (re.compile(r"sk-[a-zA-Z0-9_-]{20,}", re.IGNORECASE), "[REDACTED_API_KEY]"),
    (re.compile(r"ghp_[a-zA-Z0-9]{30,}", re.IGNORECASE), "[REDACTED_GITHUB_TOKEN]"),
    (
        re.compile(r"github_pat_[a-zA-Z0-9_]{30,}", re.IGNORECASE),
        "[REDACTED_GITHUB_PAT]",
    ),
    # DB URLs with credentials: postgresql://user:password@host
    (
        re.compile(r"(://[^:\s]+):([^@\s]+)@", re.IGNORECASE),
        r"\1:[REDACTED]@",
    ),
    # Common key-value assignments
    (
        re.compile(
            r"(?i)(api[_-]?key|access[_-]?token|secret[_-]?key|password|auth[_-]?token)\s*([:=])\s*['\"]?([^\s,;'\"]{6,})['\"]?"
        ),
        r"\1\2[REDACTED]",
    ),
    # RSA / EC / OpenSSH Private Keys
    (
        re.compile(
            r"-----BEGIN [A-Z ]+PRIVATE KEY-----[\s\S]*?-----END [A-Z ]+PRIVATE KEY-----"
        ),
        "[REDACTED_PRIVATE_KEY]",
    ),
]


def redact_secrets(text: str) -> str:
    """Scrub sensitive credentials, tokens, and keys from output text."""
    if not text:
        return text
    redacted = text
    for pattern, repl in _SECRET_PATTERNS:
        redacted = pattern.sub(repl, redacted)
    return redacted
