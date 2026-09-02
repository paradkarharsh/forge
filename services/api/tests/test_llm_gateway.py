"""Unit tests for LLMGateway retries, timeout, cancellation, error mapping, and streaming."""
import pytest

from forge_api.application.llm.gateway import LLMGateway
from forge_api.domain.audit import AuditEventType
from forge_api.domain.errors import (
    LLMAuthError,
    LLMTimeoutError,
    ModelUnavailableError,
    ProviderError,
)
from forge_api.domain.llm import (
    ChatMessage,
    MessageRole,
)
from forge_api.infrastructure.llm import FakeLLMProvider, FakeProviderConfig
from forge_api.infrastructure.llm.model_registry import ModelRegistry
from tests.conftest import FakeAuditLogger


@pytest.mark.asyncio
async def test_gateway_model_unavailable():
    registry = ModelRegistry()
    audit = FakeAuditLogger()
    gateway = LLMGateway(
        registry=registry,
        providers={"fake": FakeLLMProvider()},
        audit=audit,  # type: ignore
    )

    with pytest.raises(ModelUnavailableError):
        await gateway.complete(
            messages=[ChatMessage(role=MessageRole.USER, content="hi")],
            model="nonexistent-model",
        )


@pytest.mark.asyncio
async def test_gateway_retry_on_transient_error():
    registry = ModelRegistry()
    audit = FakeAuditLogger()

    # Configure fake provider to fail with 500 status code style error
    class TransientError(Exception):
        status_code = 503

    failing_provider = FakeLLMProvider(
        FakeProviderConfig(fail_with=TransientError("Service Unavailable"))
    )

    gateway = LLMGateway(
        registry=registry,
        providers={"fake": failing_provider},
        audit=audit,  # type: ignore
        max_retries=2,
    )

    with pytest.raises(ProviderError):
        await gateway.complete(
            messages=[ChatMessage(role=MessageRole.USER, content="hi")],
            model="fake/echo",
        )

    # 1 initial + 2 retries = 3 calls
    assert failing_provider.call_count == 3


@pytest.mark.asyncio
async def test_gateway_no_retry_on_auth_error():
    registry = ModelRegistry()
    audit = FakeAuditLogger()

    class AuthError(Exception):
        status_code = 401

    failing_provider = FakeLLMProvider(
        FakeProviderConfig(fail_with=AuthError("Unauthorized"))
    )

    gateway = LLMGateway(
        registry=registry,
        providers={"fake": failing_provider},
        audit=audit,  # type: ignore
        max_retries=3,
    )

    with pytest.raises(LLMAuthError):
        await gateway.complete(
            messages=[ChatMessage(role=MessageRole.USER, content="hi")],
            model="fake/echo",
        )

    # Should not retry auth errors
    assert failing_provider.call_count == 1


@pytest.mark.asyncio
async def test_gateway_streaming_success():
    registry = ModelRegistry()
    audit = FakeAuditLogger()

    provider = FakeLLMProvider(
        FakeProviderConfig(default_response="Hello World", stream_chunk_size=3)
    )

    gateway = LLMGateway(
        registry=registry,
        providers={"fake": provider},
        audit=audit,  # type: ignore
    )

    stream = await gateway.stream(
        messages=[ChatMessage(role=MessageRole.USER, content="hi")],
        model="fake/echo",
    )

    deltas = []
    async for delta in stream:
        if delta.content:
            deltas.append(delta.content)

    assert "".join(deltas) == "Hello World"
    assert stream.accumulated_content == "Hello World"
    assert any(e["event"] == AuditEventType.LLM_STREAM_START for e in audit.events)
    assert any(e["event"] == AuditEventType.LLM_STREAM_COMPLETE for e in audit.events)


@pytest.mark.asyncio
async def test_gateway_timeout():
    registry = ModelRegistry()
    audit = FakeAuditLogger()

    provider = FakeLLMProvider(FakeProviderConfig(timeout_seconds=0.5))

    gateway = LLMGateway(
        registry=registry,
        providers={"fake": provider},
        audit=audit,  # type: ignore
        timeout_seconds=1,  # short timeout for test
        max_retries=0,
    )

    # Fast check timeout
    gateway._timeout = 0.05

    with pytest.raises(LLMTimeoutError):
        await gateway.complete(
            messages=[ChatMessage(role=MessageRole.USER, content="hi")],
            model="fake/echo",
        )
