"""OpenAI-compatible LLM provider adapter.

Works with any OpenAI-compatible API (OpenAI, Azure, local endpoints)
via a configurable base_url.  The ``openai`` SDK is imported lazily so
it is only a runtime dependency when this provider is actually used.

Provider SDK NEVER leaks outside this module.
"""
import asyncio
import logging

from forge_api.domain.llm import (
    ChatRequest,
    ChatResponse,
    FinishReason,
    StreamDelta,
    TokenUsage,
)

logger = logging.getLogger(__name__)


def _to_finish_reason(reason: str | None) -> FinishReason:
    match reason:
        case "stop":
            return FinishReason.STOP
        case "length":
            return FinishReason.LENGTH
        case _:
            return FinishReason.STOP


class OpenAICompatibleProvider:
    """Provider adapter for OpenAI-compatible APIs.

    Requires the ``openai`` package at runtime (``pip install openai``).
    """

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        timeout: float = 120.0,
    ) -> None:
        try:
            import openai  # noqa: F811
        except ImportError as exc:
            raise ImportError(
                "The 'openai' package is required for OpenAICompatibleProvider. "
                "Install it with: pip install openai"
            ) from exc

        self._client = openai.AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
        )
        self._base_url = base_url

    @property
    def provider_name(self) -> str:
        return "openai"

    async def complete(self, request: ChatRequest) -> ChatResponse:
        import time

        messages = [
            {"role": m.role.value, "content": m.content}
            for m in request.messages
        ]
        start = time.monotonic()
        response = await self._client.chat.completions.create(
            model=request.model,
            messages=messages,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            stream=False,
        )
        duration_ms = (time.monotonic() - start) * 1000

        choice = response.choices[0]
        usage = response.usage
        return ChatResponse(
            content=choice.message.content or "",
            finish_reason=_to_finish_reason(choice.finish_reason),
            usage=TokenUsage(
                input_tokens=usage.prompt_tokens if usage else 0,
                output_tokens=usage.completion_tokens if usage else 0,
                total_tokens=usage.total_tokens if usage else 0,
            ),
            model=response.model,
            provider="openai",
            duration_ms=duration_ms,
        )

    async def stream(
        self, request: ChatRequest,
    ) -> "OpenAIStreamIterator":
        messages = [
            {"role": m.role.value, "content": m.content}
            for m in request.messages
        ]
        raw_stream = await self._client.chat.completions.create(
            model=request.model,
            messages=messages,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            stream=True,
            stream_options={"include_usage": True},
        )
        return OpenAIStreamIterator(raw_stream)

    async def health_check(self) -> bool:
        try:
            await asyncio.wait_for(
                self._client.models.list(), timeout=10.0,
            )
            return True
        except Exception:
            return False


class OpenAIStreamIterator:
    """Wraps the OpenAI streaming response into our StreamDelta protocol."""

    def __init__(self, raw_stream) -> None:
        self._stream = raw_stream
        self._done = False

    def __aiter__(self) -> "OpenAIStreamIterator":
        return self

    async def __anext__(self) -> StreamDelta:
        if self._done:
            raise StopAsyncIteration

        try:
            chunk = await self._stream.__anext__()
        except StopAsyncIteration:
            self._done = True
            raise

        if not chunk.choices:
            # Usage-only chunk at the end.
            usage = None
            if chunk.usage:
                usage = TokenUsage(
                    input_tokens=chunk.usage.prompt_tokens,
                    output_tokens=chunk.usage.completion_tokens,
                    total_tokens=chunk.usage.total_tokens,
                )
            self._done = True
            return StreamDelta(
                content="",
                finish_reason=FinishReason.STOP,
                usage=usage,
            )

        delta = chunk.choices[0].delta
        content = delta.content or "" if delta else ""
        finish = _to_finish_reason(chunk.choices[0].finish_reason)

        if chunk.choices[0].finish_reason is not None:
            usage = None
            if chunk.usage:
                usage = TokenUsage(
                    input_tokens=chunk.usage.prompt_tokens,
                    output_tokens=chunk.usage.completion_tokens,
                    total_tokens=chunk.usage.total_tokens,
                )
            return StreamDelta(
                content=content,
                finish_reason=finish,
                usage=usage,
            )

        return StreamDelta(content=content)
