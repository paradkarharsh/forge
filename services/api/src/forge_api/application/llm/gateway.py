"""LLM Gateway — the single entry point for all LLM interactions.

Responsibilities: model resolution, provider resolution, capability
validation, timeout, retries with exponential backoff, cancellation,
streaming, usage tracking, stable error mapping, and audit logging.

Retry policy:
- Retry on transient errors and provider 429/5xx.
- Do NOT retry on authentication, validation, or cancellation errors.
"""
import asyncio
import logging
import time
from typing import Any
from uuid import UUID

from forge_api.domain.audit import AuditEventType
from forge_api.domain.errors import (
    CancelledError,
    ContextTooLargeError,
    LLMAuthError,
    LLMTimeoutError,
    ModelUnavailableError,
    ProviderError,
    ProviderRateLimitedError,
    ProviderUnavailableError,
    ValidationError,
)
from forge_api.domain.llm import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    FinishReason,
    StreamDelta,
    TokenUsage,
)
from forge_api.infrastructure.audit import AuditLogger
from forge_api.infrastructure.llm.model_registry import ModelRegistry

logger = logging.getLogger(__name__)

# Errors that should NOT be retried.
_NON_RETRYABLE = (
    LLMAuthError,
    ValidationError,
    CancelledError,
    ContextTooLargeError,
    ModelUnavailableError,
    asyncio.CancelledError,
)


def _classify_provider_error(exc: Exception) -> Exception:
    """Map provider SDK exceptions into stable Forge domain errors.

    Since provider SDKs live in infrastructure, we do best-effort
    classification by attribute/class name inspection without importing
    the SDKs.
    """
    exc_type = type(exc).__name__
    exc_msg = str(exc)

    if isinstance(exc, asyncio.TimeoutError):
        return LLMTimeoutError("LLM request timed out")

    if isinstance(exc, asyncio.CancelledError):
        return CancelledError("LLM request was cancelled")

    # OpenAI SDK errors
    if "AuthenticationError" in exc_type:
        return LLMAuthError("Provider rejected API credentials")
    if "RateLimitError" in exc_type:
        return ProviderRateLimitedError("Provider rate limit exceeded")
    if "APIConnectionError" in exc_type:
        return ProviderUnavailableError("Cannot reach LLM provider")
    if "APITimeoutError" in exc_type:
        return LLMTimeoutError("LLM request timed out")

    # httpx errors (Ollama)
    if "ConnectError" in exc_type:
        return ProviderUnavailableError("Cannot reach LLM provider")
    if "TimeoutException" in exc_type or "ReadTimeout" in exc_type:
        return LLMTimeoutError("LLM request timed out")

    # HTTP status based classification
    status = getattr(exc, "status_code", None) or getattr(exc, "status", None)
    if status == 401:
        return LLMAuthError("Provider rejected API credentials")
    if status == 429:
        return ProviderRateLimitedError("Provider rate limit exceeded")
    if status and status >= 500:
        return ProviderError(f"Provider error: {exc_msg[:200]}")

    return ProviderError(f"Provider error: {exc_msg[:200]}")


def _is_retryable(exc: Exception) -> bool:
    return not isinstance(exc, _NON_RETRYABLE)


class LLMGateway:
    """Central gateway for LLM interactions.

    All provider calls flow through this gateway, which handles model
    resolution, timeout, retries, error mapping, and audit logging.
    """

    def __init__(
        self,
        *,
        registry: ModelRegistry,
        providers: dict[str, Any],
        audit: AuditLogger,
        timeout_seconds: int = 120,
        max_retries: int = 3,
    ) -> None:
        self._registry = registry
        self._providers = providers
        self._audit = audit
        self._timeout = timeout_seconds
        self._max_retries = max_retries

    def _resolve_provider(self, provider_name: str) -> Any:
        provider = self._providers.get(provider_name)
        if provider is None:
            raise ProviderUnavailableError(
                f"Provider '{provider_name}' is not configured"
            )
        return provider

    async def complete(
        self,
        *,
        messages: list[ChatMessage],
        model: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
        user_id: UUID | None = None,
    ) -> ChatResponse:
        """Run a non-streaming completion with retries."""
        spec = self._registry.resolve_model(model)
        if spec is None:
            raise ModelUnavailableError(f"Model '{model}' is not available")

        if not spec.capabilities.chat:
            raise ValidationError(f"Model '{model}' does not support chat")

        provider = self._resolve_provider(spec.provider.value)
        request = ChatRequest(
            model=model,
            messages=messages,
            temperature=temperature if temperature is not None else spec.default_temperature,
            max_tokens=max_tokens or spec.max_output_tokens,
            stream=False,
        )

        start = time.monotonic()
        last_exc: Exception | None = None

        for attempt in range(self._max_retries + 1):
            try:
                response = await asyncio.wait_for(
                    provider.complete(request),
                    timeout=self._timeout,
                )
                duration_ms = (time.monotonic() - start) * 1000

                self._audit.log(
                    AuditEventType.LLM_COMPLETION,
                    user_id=user_id,
                    payload={
                        "model": model,
                        "provider": spec.provider.value,
                        "input_tokens": response.usage.input_tokens,
                        "output_tokens": response.usage.output_tokens,
                        "duration_ms": round(duration_ms, 1),
                        "attempt": attempt + 1,
                    },
                )

                return ChatResponse(
                    content=response.content,
                    finish_reason=response.finish_reason,
                    usage=response.usage,
                    model=response.model,
                    provider=response.provider,
                    duration_ms=duration_ms,
                    metadata=response.metadata,
                )

            except Exception as exc:
                classified = _classify_provider_error(exc)
                last_exc = classified

                if not _is_retryable(classified):
                    self._audit.log(
                        AuditEventType.LLM_ERROR,
                        user_id=user_id,
                        payload={
                            "model": model,
                            "provider": spec.provider.value,
                            "error": (
                                classified.code
                                if hasattr(classified, "code")
                                else str(classified)
                            ),
                            "attempt": attempt + 1,
                        },
                    )
                    raise classified from exc

                if attempt < self._max_retries:
                    delay = min(2 ** attempt, 30)
                    logger.warning(
                        "LLM retry %d/%d for %s: %s (backoff %.1fs)",
                        attempt + 1, self._max_retries, model,
                        str(exc)[:100], delay,
                    )
                    await asyncio.sleep(delay)

        self._audit.log(
            AuditEventType.LLM_ERROR,
            user_id=user_id,
            payload={
                "model": model,
                "provider": spec.provider.value,
                "error": "max_retries_exceeded",
                "attempts": self._max_retries + 1,
            },
        )
        raise last_exc  # type: ignore[misc]

    async def stream(
        self,
        *,
        messages: list[ChatMessage],
        model: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
        user_id: UUID | None = None,
    ) -> "GatewayStreamIterator":
        """Start a streaming completion. Returns an async iterator."""
        spec = self._registry.resolve_model(model)
        if spec is None:
            raise ModelUnavailableError(f"Model '{model}' is not available")

        if not spec.capabilities.streaming:
            raise ValidationError(f"Model '{model}' does not support streaming")

        provider = self._resolve_provider(spec.provider.value)
        request = ChatRequest(
            model=model,
            messages=messages,
            temperature=temperature if temperature is not None else spec.default_temperature,
            max_tokens=max_tokens or spec.max_output_tokens,
            stream=True,
        )

        try:
            raw_stream = await asyncio.wait_for(
                provider.stream(request),
                timeout=self._timeout,
            )
        except Exception as exc:
            classified = _classify_provider_error(exc)
            self._audit.log(
                AuditEventType.LLM_STREAM_ERROR,
                user_id=user_id,
                payload={
                    "model": model,
                    "provider": spec.provider.value,
                    "error": classified.code if hasattr(classified, "code") else str(classified),
                },
            )
            raise classified from exc

        self._audit.log(
            AuditEventType.LLM_STREAM_START,
            user_id=user_id,
            payload={
                "model": model,
                "provider": spec.provider.value,
            },
        )

        return GatewayStreamIterator(
            raw_stream=raw_stream,
            model=model,
            provider=spec.provider.value,
            user_id=user_id,
            audit=self._audit,
        )


class GatewayStreamIterator:
    """Wraps a provider stream iterator with audit and error mapping."""

    def __init__(
        self,
        *,
        raw_stream: Any,
        model: str,
        provider: str,
        user_id: UUID | None,
        audit: AuditLogger,
    ) -> None:
        self._stream = raw_stream
        self._model = model
        self._provider = provider
        self._user_id = user_id
        self._audit = audit
        self._accumulated = ""
        self._usage: TokenUsage | None = None
        self._finish_reason: FinishReason | None = None
        self._done = False
        self._start = time.monotonic()

    @property
    def accumulated_content(self) -> str:
        return self._accumulated

    @property
    def usage(self) -> TokenUsage | None:
        return self._usage

    @property
    def finish_reason(self) -> FinishReason | None:
        return self._finish_reason

    @property
    def duration_ms(self) -> float:
        return (time.monotonic() - self._start) * 1000

    def __aiter__(self) -> "GatewayStreamIterator":
        return self

    async def __anext__(self) -> StreamDelta:
        if self._done:
            raise StopAsyncIteration

        try:
            delta = await self._stream.__anext__()
        except StopAsyncIteration:
            self._done = True
            self._audit.log(
                AuditEventType.LLM_STREAM_COMPLETE,
                user_id=self._user_id,
                payload={
                    "model": self._model,
                    "provider": self._provider,
                    "content_length": len(self._accumulated),
                    "duration_ms": round(self.duration_ms, 1),
                },
            )
            raise
        except asyncio.CancelledError:
            self._done = True
            self._finish_reason = FinishReason.CANCELLED
            self._audit.log(
                AuditEventType.LLM_CANCELLED,
                user_id=self._user_id,
                payload={
                    "model": self._model,
                    "provider": self._provider,
                    "partial_content_length": len(self._accumulated),
                },
            )
            raise
        except Exception as exc:
            self._done = True
            classified = _classify_provider_error(exc)
            self._finish_reason = FinishReason.ERROR
            self._audit.log(
                AuditEventType.LLM_STREAM_ERROR,
                user_id=self._user_id,
                payload={
                    "model": self._model,
                    "provider": self._provider,
                    "error": str(classified)[:200],
                },
            )
            raise classified from exc

        if delta.content:
            self._accumulated += delta.content
        if delta.usage is not None:
            self._usage = delta.usage
        if delta.finish_reason is not None:
            self._finish_reason = delta.finish_reason

        return delta
