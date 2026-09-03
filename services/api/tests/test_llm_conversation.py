"""Unit and integration tests for ConversationService, conversation API, and streaming SSE."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from forge_api.application.llm.conversation_service import ConversationService
from forge_api.application.llm.gateway import LLMGateway
from forge_api.application.llm.prompt_builder import PromptBuilder
from forge_api.application.llm.usage_tracker import UsageTracker
from forge_api.domain.conversation import (
    ConversationRecord,
    ConversationStatus,
    MessageRecord,
    MessageStatus,
    UsageEventRecord,
)
from forge_api.domain.errors import AuthorizationError
from forge_api.domain.llm import TokenUsage
from forge_api.domain.memory import (
    ContextEntry,
    ContextSource,
    ContextWindow,
    ConversationContextEntry,
    MemoryScope,
)
from forge_api.domain.security import AccessClaims
from forge_api.infrastructure.llm import FakeLLMProvider, FakeProviderConfig
from forge_api.infrastructure.llm.model_registry import ModelRegistry
from tests.conftest import (
    FakeAuditLogger,
    FakeConversationContextStore,
    FakeSessionRepository,
    FakeUserRepository,
    FakeWorkspaceRepository,
)

# ─── Fake Repositories for FP7 ────────────────────────────────────────


class FakeConversationRepository:
    def __init__(self) -> None:
        self.conversations: dict[UUID, ConversationRecord] = {}

    async def get(self, conversation_id: UUID) -> ConversationRecord | None:
        return self.conversations.get(conversation_id)

    async def list_by_workspace(
        self,
        workspace_id: UUID,
        user_id: UUID,
        *,
        limit: int = 50,
        offset: int = 0,
        include_deleted: bool = False,
    ) -> list[ConversationRecord]:
        results = [
            c
            for c in self.conversations.values()
            if c.workspace_id == workspace_id
            and c.user_id == user_id
            and (include_deleted or c.deleted_at is None)
        ]
        results.sort(key=lambda c: c.created_at, reverse=True)
        return results[offset : offset + limit]

    async def count_by_workspace(
        self,
        workspace_id: UUID,
        user_id: UUID,
        *,
        include_deleted: bool = False,
    ) -> int:
        return len(
            [
                c
                for c in self.conversations.values()
                if c.workspace_id == workspace_id
                and c.user_id == user_id
                and (include_deleted or c.deleted_at is None)
            ]
        )

    async def create(
        self,
        *,
        workspace_id: UUID,
        user_id: UUID,
        title: str | None = None,
        repository_id: UUID | None = None,
    ) -> ConversationRecord:
        cid = uuid4()
        now = datetime.now(UTC)
        record = ConversationRecord(
            id=cid,
            workspace_id=workspace_id,
            user_id=user_id,
            title=title,
            repository_id=repository_id,
            status=ConversationStatus.ACTIVE,
            message_count=0,
            created_at=now,
            updated_at=now,
            deleted_at=None,
        )
        self.conversations[cid] = record
        return record

    async def update_title(self, conversation_id: UUID, title: str) -> ConversationRecord | None:
        conv = self.conversations.get(conversation_id)
        if not conv:
            return None
        updated = ConversationRecord(
            id=conv.id,
            workspace_id=conv.workspace_id,
            user_id=conv.user_id,
            title=title,
            repository_id=conv.repository_id,
            status=conv.status,
            message_count=conv.message_count,
            created_at=conv.created_at,
            updated_at=datetime.now(UTC),
            deleted_at=conv.deleted_at,
        )
        self.conversations[conversation_id] = updated
        return updated

    async def increment_message_count(self, conversation_id: UUID) -> bool:
        conv = self.conversations.get(conversation_id)
        if not conv:
            return False
        self.conversations[conversation_id] = ConversationRecord(
            id=conv.id,
            workspace_id=conv.workspace_id,
            user_id=conv.user_id,
            title=conv.title,
            repository_id=conv.repository_id,
            status=conv.status,
            message_count=conv.message_count + 1,
            created_at=conv.created_at,
            updated_at=datetime.now(UTC),
            deleted_at=conv.deleted_at,
        )
        return True

    async def soft_delete(self, conversation_id: UUID) -> bool:
        conv = self.conversations.get(conversation_id)
        if not conv or conv.deleted_at is not None:
            return False
        self.conversations[conversation_id] = ConversationRecord(
            id=conv.id,
            workspace_id=conv.workspace_id,
            user_id=conv.user_id,
            title=conv.title,
            repository_id=conv.repository_id,
            status=conv.status,
            message_count=conv.message_count,
            created_at=conv.created_at,
            updated_at=datetime.now(UTC),
            deleted_at=datetime.now(UTC),
        )
        return True


class FakeMessageRepository:
    def __init__(self) -> None:
        self.messages: dict[UUID, MessageRecord] = {}

    async def get(self, message_id: UUID) -> MessageRecord | None:
        return self.messages.get(message_id)

    async def list_by_conversation(
        self,
        conversation_id: UUID,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[MessageRecord]:
        res = [m for m in self.messages.values() if m.conversation_id == conversation_id]
        res.sort(key=lambda m: m.created_at)
        return res[offset : offset + limit]

    async def count_by_conversation(self, conversation_id: UUID) -> int:
        return len([m for m in self.messages.values() if m.conversation_id == conversation_id])

    async def create(
        self,
        *,
        conversation_id: UUID,
        role: str,
        content: str,
        provider: str | None = None,
        model: str | None = None,
        prompt_version: str | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        total_tokens: int | None = None,
        duration_ms: float | None = None,
        finish_reason: str | None = None,
        status: str = "complete",
        metadata: dict | None = None,
    ) -> MessageRecord:
        mid = uuid4()
        record = MessageRecord(
            id=mid,
            conversation_id=conversation_id,
            role=role,
            content=content,
            provider=provider,
            model=model,
            prompt_version=prompt_version,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            duration_ms=duration_ms,
            finish_reason=finish_reason,
            status=(
                MessageStatus(status)
                if status in ("complete", "partial", "cancelled", "error")
                else MessageStatus.COMPLETE
            ),
            metadata=metadata or {},
            created_at=datetime.now(UTC),
        )
        self.messages[mid] = record
        return record

    async def update(
        self,
        message_id: UUID,
        *,
        content: str | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        total_tokens: int | None = None,
        duration_ms: float | None = None,
        finish_reason: str | None = None,
        status: str | None = None,
        metadata: dict | None = None,
    ) -> MessageRecord | None:
        msg = self.messages.get(message_id)
        if not msg:
            return None
        updated = MessageRecord(
            id=msg.id,
            conversation_id=msg.conversation_id,
            role=msg.role,
            content=content if content is not None else msg.content,
            provider=msg.provider,
            model=msg.model,
            prompt_version=msg.prompt_version,
            input_tokens=input_tokens if input_tokens is not None else msg.input_tokens,
            output_tokens=output_tokens if output_tokens is not None else msg.output_tokens,
            total_tokens=total_tokens if total_tokens is not None else msg.total_tokens,
            duration_ms=duration_ms if duration_ms is not None else msg.duration_ms,
            finish_reason=finish_reason if finish_reason is not None else msg.finish_reason,
            status=MessageStatus(status) if status else msg.status,
            metadata=metadata if metadata is not None else msg.metadata,
            created_at=msg.created_at,
        )
        self.messages[message_id] = updated
        return updated


class FakeUsageEventRepository:
    def __init__(self) -> None:
        self.events: list[UsageEventRecord] = []

    async def create(
        self,
        *,
        workspace_id: UUID,
        user_id: UUID,
        conversation_id: UUID | None = None,
        message_id: UUID | None = None,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        total_tokens: int,
        duration_ms: float,
        estimated_cost: float = 0.0,
        agent_session_id: UUID | None = None,
        metadata: dict | None = None,
    ) -> UsageEventRecord:
        record = UsageEventRecord(
            id=uuid4(),
            workspace_id=workspace_id,
            user_id=user_id,
            conversation_id=conversation_id,
            message_id=message_id,
            agent_session_id=agent_session_id,
            provider=provider,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            duration_ms=duration_ms,
            estimated_cost=estimated_cost,
            created_at=datetime.now(UTC),
            metadata=metadata or {},
        )

        self.events.append(record)
        return record

    async def list_by_workspace(
        self,
        workspace_id: UUID,
        user_id: UUID | None = None,
        *,
        limit: int = 50,
        offset: int = 0,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> list[UsageEventRecord]:
        filtered = [
            e
            for e in self.events
            if e.workspace_id == workspace_id
            and (user_id is None or e.user_id == user_id)
            and (start_time is None or e.created_at >= start_time)
            and (end_time is None or e.created_at <= end_time)
        ]
        return filtered[offset : offset + limit]

    async def count_by_workspace(
        self,
        workspace_id: UUID,
        user_id: UUID | None = None,
        *,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> int:
        return len(
            [
                e
                for e in self.events
                if e.workspace_id == workspace_id
                and (user_id is None or e.user_id == user_id)
                and (start_time is None or e.created_at >= start_time)
                and (end_time is None or e.created_at <= end_time)
            ]
        )

    async def aggregate_by_workspace(
        self,
        workspace_id: UUID,
        user_id: UUID | None = None,
        *,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> dict:
        events = await self.list_by_workspace(
            workspace_id, user_id, limit=10000, start_time=start_time, end_time=end_time
        )
        return {
            "total_input_tokens": sum(e.input_tokens for e in events),
            "total_output_tokens": sum(e.output_tokens for e in events),
            "total_tokens": sum(e.total_tokens for e in events),
            "total_cost": sum(e.estimated_cost for e in events),
            "event_count": len(events),
        }


# ─── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def fake_repos():
    return {
        "users": FakeUserRepository(),
        "sessions": FakeSessionRepository(),
        "workspaces": FakeWorkspaceRepository(),
        "conversations": FakeConversationRepository(),
        "messages": FakeMessageRepository(),
        "usage_events": FakeUsageEventRepository(),
        "audit": FakeAuditLogger(),
        "registry": ModelRegistry(),
    }


def _create_service(fake_repos, fake_provider=None) -> ConversationService:
    provider = fake_provider or FakeLLMProvider()
    gateway = LLMGateway(
        registry=fake_repos["registry"],
        providers={"fake": provider},
        audit=fake_repos["audit"],
    )
    usage_tracker = UsageTracker(
        usage_repo=fake_repos["usage_events"],
        registry=fake_repos["registry"],
    )
    return ConversationService(
        conversations=fake_repos["conversations"],
        messages=fake_repos["messages"],
        usage_events=fake_repos["usage_events"],
        gateway=gateway,
        prompt_builder=PromptBuilder(version="1.0.0"),
        usage_tracker=usage_tracker,
        registry=fake_repos["registry"],
        audit=fake_repos["audit"],
    )


# ─── Unit Tests ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_conversation_service_crud_and_authorization(fake_repos):
    """Verify conversation CRUD with strict authorization and workspace isolation."""
    svc = _create_service(fake_repos)
    ws_id = uuid4()
    other_ws_id = uuid4()
    user_id = uuid4()
    other_user_id = uuid4()

    # Create conversation
    conv = await svc.create_conversation(
        workspace_id=ws_id,
        user_id=user_id,
        title="My Feature Plan",
    )
    assert conv.title == "My Feature Plan"
    assert conv.workspace_id == ws_id
    assert conv.user_id == user_id
    assert conv.message_count == 0

    # Get conversation as owner
    fetched = await svc.get_conversation(
        conversation_id=conv.id,
        workspace_id=ws_id,
        user_id=user_id,
    )
    assert fetched.id == conv.id

    # Cross-workspace access rejected
    with pytest.raises(AuthorizationError):
        await svc.get_conversation(
            conversation_id=conv.id,
            workspace_id=other_ws_id,
            user_id=user_id,
        )

    # Modification access by non-owner rejected
    with pytest.raises(AuthorizationError):
        await svc.get_conversation(
            conversation_id=conv.id,
            workspace_id=ws_id,
            user_id=other_user_id,
            require_owner=True,
        )

    # Non-owner deletion rejected
    with pytest.raises(AuthorizationError):
        await svc.delete_conversation(
            conversation_id=conv.id,
            workspace_id=ws_id,
            user_id=other_user_id,
        )

    # Owner delete succeeds
    assert (
        await svc.delete_conversation(
            conversation_id=conv.id,
            workspace_id=ws_id,
            user_id=user_id,
        )
        is True
    )


@pytest.mark.asyncio
async def test_conversation_completion_with_context_and_usage(fake_repos):
    """Verify non-streaming completion with prompt construction, persistence, and usage tracking."""
    fake_provider = FakeLLMProvider(
        FakeProviderConfig(
            default_response="Here is the refactored code.",
            default_usage=TokenUsage(input_tokens=15, output_tokens=25, total_tokens=40),
        )
    )
    svc = _create_service(fake_repos, fake_provider)
    ws_id = uuid4()
    user_id = uuid4()

    conv = await svc.create_conversation(workspace_id=ws_id, user_id=user_id, title="Refactor")

    ctx_window = ContextWindow(
        entries=(
            ContextEntry(
                source=ContextSource.REPOSITORY_FILE,
                scope=MemoryScope.REPOSITORY,
                content="def old(): pass",
                relevance_score=0.9,
                source_id=None,
                file_path="src/old.py",
                metadata={},
            ),
        ),
        total_tokens=50,
        truncated=False,
        repository_id=None,
        workspace_id=ws_id,
        assembled_at=datetime.now(UTC),
    )

    user_msg, assistant_msg = await svc.complete(
        conversation_id=conv.id,
        workspace_id=ws_id,
        user_id=user_id,
        user_message="Please refactor old()",
        context_window=ctx_window,
        model="fake/echo",
    )

    assert user_msg.role == "user"
    assert user_msg.content == "Please refactor old()"
    assert assistant_msg.role == "assistant"
    assert assistant_msg.content == "Here is the refactored code."
    assert assistant_msg.input_tokens == 15
    assert assistant_msg.output_tokens == 25
    assert assistant_msg.total_tokens == 40
    assert assistant_msg.status == MessageStatus.COMPLETE

    # Verify message persistence and count
    messages = await svc.list_messages(
        conversation_id=conv.id,
        workspace_id=ws_id,
        user_id=user_id,
    )
    assert len(messages) == 2
    count = await svc.count_messages(
        conversation_id=conv.id,
        workspace_id=ws_id,
        user_id=user_id,
    )
    assert count == 2

    # Verify usage was tracked
    usage_events = fake_repos["usage_events"].events
    assert len(usage_events) == 1
    assert usage_events[0].workspace_id == ws_id
    assert usage_events[0].total_tokens == 40


@pytest.mark.asyncio
async def test_conversation_streaming_lifecycle(fake_repos):
    """Verify streaming completion lifecycle: start delta, accumulation, finalize, and usage."""
    fake_provider = FakeLLMProvider(
        FakeProviderConfig(
            default_response="Streaming answer for test.",
            stream_chunk_size=7,
            default_usage=TokenUsage(input_tokens=10, output_tokens=20, total_tokens=30),
        )
    )
    svc = _create_service(fake_repos, fake_provider)
    ws_id = uuid4()
    user_id = uuid4()

    conv = await svc.create_conversation(workspace_id=ws_id, user_id=user_id)

    stream = await svc.stream(
        conversation_id=conv.id,
        workspace_id=ws_id,
        user_id=user_id,
        user_message="Stream to me",
        model="fake/echo",
    )

    events = []
    async for event in stream:
        events.append(event)

    # Should yield deltas and final done event
    assert any(e["event"] == "delta" for e in events)
    assert events[-1]["event"] == "done"
    assert events[-1]["data"]["finish_reason"] == "stop"

    # Verify assistant message was persisted with full accumulated text
    messages = await svc.list_messages(
        conversation_id=conv.id,
        workspace_id=ws_id,
        user_id=user_id,
    )
    assert len(messages) == 2
    assert messages[1].content == "Streaming answer for test."
    assert messages[1].status == MessageStatus.COMPLETE


@pytest.mark.asyncio
async def test_conversation_streaming_cancellation(fake_repos):
    """Verify stream cancellation persists partial assistant content and marks status cancelled."""
    fake_provider = FakeLLMProvider(
        FakeProviderConfig(
            default_response="Part 1 and Part 2 and Part 3",
            stream_chunk_size=6,
        )
    )
    svc = _create_service(fake_repos, fake_provider)
    ws_id = uuid4()
    user_id = uuid4()

    conv = await svc.create_conversation(workspace_id=ws_id, user_id=user_id)

    stream = await svc.stream(
        conversation_id=conv.id,
        workspace_id=ws_id,
        user_id=user_id,
        user_message="Long stream",
        model="fake/echo",
    )

    # Consume first chunk then cancel
    first_chunk = await stream.__anext__()
    assert first_chunk["event"] == "delta"
    await stream.cancel()

    # Verify cancellation persisted partial content
    assistant_record = await fake_repos["messages"].get(stream.message_id)
    assert assistant_record is not None
    assert assistant_record.finish_reason == "cancelled"
    assert assistant_record.status == MessageStatus.PARTIAL


@pytest.mark.asyncio
async def test_fp6_redis_vs_fp7_postgres_separation():
    """Verify Redis ephemeral conversation context remains decoupled from PostgreSQL history."""
    redis_store = FakeConversationContextStore()
    postgres_repo = FakeConversationRepository()
    session_id = uuid4()
    conv_id = uuid4()

    # Append to Redis ephemeral context (FP6)
    await redis_store.append(
        session_id=session_id,
        conversation_id=conv_id,
        entry=ConversationContextEntry(
            role="user",
            content="Ephemeral turn",
            timestamp=datetime.now(UTC),
        ),
    )
    redis_entries = await redis_store.get(session_id, conv_id)
    assert len(redis_entries) == 1
    assert redis_entries[0].content == "Ephemeral turn"

    # PostgreSQL repository (FP7) remains clean and unaffected
    conv = await postgres_repo.get(conv_id)
    assert conv is None


# ─── HTTP API Tests ───────────────────────────────────────────────────


def test_llm_models_endpoint(test_client, fake_repos):
    """Verify GET /v1/llm/models returns available models."""
    user_id = uuid4()
    session_id = uuid4()
    claims = AccessClaims(user_id=user_id, session_id=session_id)

    from forge_api.presentation.http.dependencies import validated_claims

    test_client.app.dependency_overrides[validated_claims] = lambda: claims

    response = test_client.get("/v1/llm/models")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    model_ids = [m["model_id"] for m in data["data"]]
    assert "fake/echo" in model_ids
    assert "gpt-4o" in model_ids

    test_client.app.dependency_overrides.clear()


def test_stateless_complete(test_client):
    """Verify POST /v1/llm/complete performs a stateless completion."""
    user_id = uuid4()
    session_id = uuid4()
    claims = AccessClaims(user_id=user_id, session_id=session_id)

    from forge_api.presentation.http.dependencies import validated_claims

    test_client.app.dependency_overrides[validated_claims] = lambda: claims

    response = test_client.post(
        "/v1/llm/complete",
        json={
            "model": "fake/echo",
            "messages": [{"role": "user", "content": "Hello"}],
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["content"] == "This is a fake response from Forge AI."
    assert data["data"]["model"] == "fake/echo"
    assert data["data"]["finish_reason"] == "stop"

    test_client.app.dependency_overrides.clear()


def test_stateless_complete_validation_error(test_client):
    """Verify invalid requests return 404 error contract for unavailable models."""
    user_id = uuid4()
    session_id = uuid4()
    claims = AccessClaims(user_id=user_id, session_id=session_id)

    from forge_api.presentation.http.dependencies import validated_claims

    test_client.app.dependency_overrides[validated_claims] = lambda: claims

    response = test_client.post(
        "/v1/llm/complete",
        json={
            "model": "invalid-model",
            "messages": [{"role": "user", "content": "Hello"}],
        },
    )
    assert response.status_code == 404
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "model_unavailable"

    test_client.app.dependency_overrides.clear()
