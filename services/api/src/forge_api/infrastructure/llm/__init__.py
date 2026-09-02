"""Fake LLM provider for deterministic testing.

Supports configurable completions, streaming deltas, usage, failures,
timeouts, and cancellation testing.  No network access required.
"""
import asyncio
from dataclasses import dataclass, field

from forge_api.domain.llm import (
    ChatRequest,
    ChatResponse,
    FinishReason,
    StreamDelta,
    TokenUsage,
)


@dataclass
class FakeProviderConfig:
    """Configurable behaviour for FakeLLMProvider."""

    default_response: str = "This is a fake response from Forge AI."
    default_model: str = "fake/echo"
    default_finish_reason: FinishReason = FinishReason.STOP
    default_usage: TokenUsage = field(
        default_factory=lambda: TokenUsage(
            input_tokens=10, output_tokens=20, total_tokens=30,
        )
    )
    stream_chunk_size: int = 5
    stream_delay_seconds: float = 0.0
    fail_with: Exception | None = None
    fail_after_chunks: int | None = None
    timeout_seconds: float | None = None
    responses: dict[str, str] = field(default_factory=dict)


class FakeLLMProvider:
    """Deterministic LLM provider for automated tests.

    All completions are deterministic.  No network, no API key, no
    external dependency.
    """

    def __init__(self, config: FakeProviderConfig | None = None) -> None:
        self._config = config or FakeProviderConfig()
        self._call_count = 0
        self._last_request: ChatRequest | None = None

    @property
    def provider_name(self) -> str:
        return "fake"

    @property
    def call_count(self) -> int:
        return self._call_count

    @property
    def last_request(self) -> ChatRequest | None:
        return self._last_request

    def _resolve_response(self, request: ChatRequest) -> str:
        # Check custom responses by model name first.
        if request.model in self._config.responses:
            return self._config.responses[request.model]
        # Then check if the last user message matches a key.
        for msg in reversed(request.messages):
            if msg.role.value == "user" and msg.content in self._config.responses:
                return self._config.responses[msg.content]
        return self._config.default_response

    async def complete(self, request: ChatRequest) -> ChatResponse:
        self._call_count += 1
        self._last_request = request

        if self._config.timeout_seconds is not None:
            await asyncio.sleep(self._config.timeout_seconds)

        if self._config.fail_with is not None:
            raise self._config.fail_with

        content = self._resolve_response(request)
        return ChatResponse(
            content=content,
            finish_reason=self._config.default_finish_reason,
            usage=self._config.default_usage,
            model=request.model or self._config.default_model,
            provider="fake",
        )

    async def stream(self, request: ChatRequest) -> "FakeStreamIterator":
        self._call_count += 1
        self._last_request = request

        if self._config.timeout_seconds is not None:
            await asyncio.sleep(self._config.timeout_seconds)

        if self._config.fail_with is not None:
            raise self._config.fail_with

        content = self._resolve_response(request)
        return FakeStreamIterator(
            content=content,
            chunk_size=self._config.stream_chunk_size,
            delay=self._config.stream_delay_seconds,
            usage=self._config.default_usage,
            fail_with=self._config.fail_with,
            fail_after_chunks=self._config.fail_after_chunks,
        )

    async def health_check(self) -> bool:
        return self._config.fail_with is None


class FakeStreamIterator:
    """Async iterator that yields deterministic stream deltas."""

    def __init__(
        self,
        content: str,
        chunk_size: int = 5,
        delay: float = 0.0,
        usage: TokenUsage | None = None,
        fail_with: Exception | None = None,
        fail_after_chunks: int | None = None,
    ) -> None:
        self._chunks = [
            content[i : i + chunk_size]
            for i in range(0, max(1, len(content)), chunk_size)
        ]
        if not content:
            self._chunks = [""]
        self._index = 0
        self._delay = delay
        self._usage = usage or TokenUsage()
        self._fail_with = fail_with
        self._fail_after_chunks = fail_after_chunks
        self._done = False

    def __aiter__(self) -> "FakeStreamIterator":
        return self

    async def __anext__(self) -> StreamDelta:
        if self._done:
            raise StopAsyncIteration

        if self._delay > 0:
            await asyncio.sleep(self._delay)

        if (
            self._fail_after_chunks is not None
            and self._index >= self._fail_after_chunks
            and self._fail_with is not None
        ):
            raise self._fail_with

        if self._index < len(self._chunks):
            chunk = self._chunks[self._index]
            self._index += 1
            return StreamDelta(content=chunk)

        # Final delta with usage and finish reason.
        self._done = True
        return StreamDelta(
            content="",
            finish_reason=FinishReason.STOP,
            usage=self._usage,
        )
