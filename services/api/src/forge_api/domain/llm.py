"""LLM domain model.

Provider-neutral records, enums, and protocols for AI model interaction.
Provider SDKs or client libraries must NEVER appear in this module.
"""
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

# ─── Enums ────────────────────────────────────────────────────────────


class MessageRole(StrEnum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class FinishReason(StrEnum):
    STOP = "stop"
    LENGTH = "length"
    CANCELLED = "cancelled"
    ERROR = "error"


class LLMProviderType(StrEnum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OLLAMA = "ollama"
    FAKE = "fake"


# ─── Records ──────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class TokenUsage:
    """Token usage for a single LLM call."""

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


@dataclass(frozen=True, slots=True)
class ModelCapabilities:
    """What a model can do."""

    chat: bool = True
    streaming: bool = True
    system_prompt: bool = True
    # Future compatibility — defined but NOT implemented in FP7.
    tool_calling: bool = False
    structured_output: bool = False


@dataclass(frozen=True, slots=True)
class ModelSpec:
    """Registry entry for a configured model."""

    provider: LLMProviderType
    model_id: str
    display_name: str
    capabilities: ModelCapabilities
    context_window: int = 4096
    max_output_tokens: int = 4096
    default_temperature: float = 0.7
    input_cost_per_million: float = 0.0
    output_cost_per_million: float = 0.0
    enabled: bool = True
    availability: str = "available"


@dataclass(frozen=True, slots=True)
class ChatMessage:
    """A single message in a chat sequence."""

    role: MessageRole
    content: str


@dataclass(frozen=True, slots=True)
class ChatRequest:
    """Provider-neutral chat completion request."""

    model: str
    messages: list[ChatMessage]
    temperature: float = 0.7
    max_tokens: int | None = None
    stream: bool = False
    # Future compatibility — defined but NOT implemented in FP7.
    tools: list[dict[str, Any]] | None = None


@dataclass(frozen=True, slots=True)
class StreamDelta:
    """A single streaming chunk from the provider."""

    content: str = ""
    finish_reason: FinishReason | None = None
    usage: TokenUsage | None = None


@dataclass(frozen=True, slots=True)
class ChatResponse:
    """Provider-neutral chat completion response."""

    content: str
    finish_reason: FinishReason
    usage: TokenUsage
    model: str
    provider: str
    duration_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


# ─── Tool spec — future compatibility only ────────────────────────────


@dataclass(frozen=True, slots=True)
class ToolSpec:
    """Definition of a tool an LLM may call.

    Defined for future compatibility; FP7 does NOT implement tool
    execution, dispatch, or any autonomous actions.
    """

    name: str
    description: str
    parameters_schema: dict[str, Any] = field(default_factory=dict)


# ─── Provider port ────────────────────────────────────────────────────


@runtime_checkable
class LLMProvider(Protocol):
    """Adapter port for an LLM provider.

    Infrastructure layer implementations translate this protocol into
    the concrete provider SDK calls (OpenAI, Ollama, etc.).  Domain and
    application layers depend only on this protocol.
    """

    @property
    def provider_name(self) -> str:
        """Stable identifier for this provider (e.g. 'openai', 'ollama')."""
        ...

    async def complete(self, request: ChatRequest) -> ChatResponse:
        """Run a non-streaming completion."""
        ...

    async def stream(
        self, request: ChatRequest,
    ) -> "AsyncStreamIterator":
        """Return an async iterator of StreamDelta values."""
        ...

    async def health_check(self) -> bool:
        """Return True if the provider is reachable."""
        ...


class AsyncStreamIterator(Protocol):
    """Async iterator protocol for streaming deltas."""

    def __aiter__(self) -> "AsyncStreamIterator": ...

    async def __anext__(self) -> StreamDelta: ...


# ─── Error codes ──────────────────────────────────────────────────────
# Stable error codes for the LLM subsystem.  Reused by the application
# gateway and presentation error mappers.

LLM_ERROR_CODES = {
    "provider_unavailable": 503,
    "llm_auth_failed": 401,
    "provider_rate_limited": 429,
    "llm_timeout": 504,
    "context_too_large": 422,
    "model_unavailable": 404,
    "provider_error": 502,
    "cancelled": 499,
}


# ─── Prompt section ordering ─────────────────────────────────────────


class PromptSection(StrEnum):
    """Canonical ordering of prompt sections in the prompt builder."""

    SYSTEM = "system"
    PROJECT = "project"
    REPOSITORY = "repository"
    MEMORY = "memory"
    CONVERSATION = "conversation"
    USER = "user"
