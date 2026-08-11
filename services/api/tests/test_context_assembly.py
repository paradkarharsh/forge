"""ContextAssemblyService unit tests.

Covers fan-out retrieval from memory + repository intelligence +
conversation context, ranking, deduplication, truncation, scope filtering,
and graceful fallback when embeddings are unavailable.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from forge_api.application.indexing.search_service import SearchService
from forge_api.application.memory.context_assembly_service import (
    ContextAssemblyService,
)
from forge_api.domain.auth import WorkspaceRole
from forge_api.domain.errors import AuthorizationError, ValidationError
from forge_api.domain.memory import (
    ContextRankingConfig,
    ContextSource,
    MemoryScope,
)
from forge_api.infrastructure.embedding import NullEmbedder


class _FakeRepoRepo:
    """Minimal RepositoryRepository for SearchService construction."""

    async def get(self, repository_id):
        return None


def _build_assembly(
    fake_memories,
    fake_workspaces,
    fake_audit,
    fake_conversation,
    search,
    embedding=None,
    *,
    min_relevance=0.0,
    max_tokens=8192,
):
    return ContextAssemblyService(
        memories=fake_memories,
        search=search,
        conversation=fake_conversation,
        embedding=embedding or NullEmbedder(),
        workspaces=fake_workspaces,
        audit=fake_audit,
        ranking=ContextRankingConfig(),
        max_tokens=max_tokens,
        min_relevance=min_relevance,
        conversation_max_entries=100,
    )


def _build_search(fake_workspaces, *, embedding=None):
    from tests.conftest import (
        FakeRepositoryChunkRepository,
        FakeRepositoryDependencyRepository,
        FakeRepositoryFileRepository,
        FakeRepositorySymbolRepository,
    )

    return SearchService(
        repositories=_FakeRepoRepo(),
        files=FakeRepositoryFileRepository(),
        symbols=FakeRepositorySymbolRepository(),
        dependencies=FakeRepositoryDependencyRepository(),
        chunks=FakeRepositoryChunkRepository(),
        workspaces=fake_workspaces,
        embedding=embedding or NullEmbedder(),
    )


async def _seeded(
    fake_memories,
    fake_workspaces,
    fake_audit,
    fake_conversation,
    embedding=None,
):
    wid = uuid4()
    uid = uuid4()
    await fake_workspaces.create(name="w", slug="w")
    await fake_workspaces.add_member(workspace_id=wid, user_id=uid, role=WorkspaceRole.OWNER)
    await fake_memories.create(
        workspace_id=wid,
        memory_type="decision",
        scope="workspace",
        content="use repository ports",
        tags=["architecture"],
    )
    await fake_memories.create(
        workspace_id=wid,
        memory_type="preference",
        scope="user",
        user_id=uid,
        content="prefer async",
        tags=["pref"],
    )
    search = _build_search(fake_workspaces, embedding=embedding)
    svc = _build_assembly(
        fake_memories,
        fake_workspaces,
        fake_audit,
        fake_conversation,
        search,
        embedding=embedding,
    )
    return svc, wid, uid


@pytest.mark.asyncio
async def test_assemble_requires_membership(
    fake_memories,
    fake_workspaces,
    fake_audit,
    fake_conversation,
):
    svc, wid, _ = await _seeded(
        fake_memories,
        fake_workspaces,
        fake_audit,
        fake_conversation,
    )
    with pytest.raises(AuthorizationError):
        await svc.assemble(workspace_id=wid, user_id=uuid4(), query="ports")


@pytest.mark.asyncio
async def test_assemble_returns_memory_and_conversation_context(
    fake_memories,
    fake_workspaces,
    fake_audit,
    fake_conversation,
):
    svc, wid, uid = await _seeded(
        fake_memories,
        fake_workspaces,
        fake_audit,
        fake_conversation,
    )
    # Append a conversation entry.
    from forge_api.domain.memory import ConversationContextEntry

    conv_id = uuid4()
    session_id = uuid4()
    await fake_conversation.append(
        session_id,
        conv_id,
        ConversationContextEntry(
            role="user", content="what is the port pattern?", timestamp=datetime.now(UTC)
        ),
    )
    window = await svc.assemble(
        workspace_id=wid,
        user_id=uid,
        query="ports",
        session_id=session_id,
        conversation_id=conv_id,
    )
    sources = {e.source for e in window.entries}
    assert ContextSource.MEMORY in sources
    assert ContextSource.CONVERSATION in sources
    assert window.workspace_id == wid


@pytest.mark.asyncio
async def test_assemble_excludes_other_users_memories(
    fake_memories,
    fake_workspaces,
    fake_audit,
    fake_conversation,
):
    wid = uuid4()
    uid1 = uuid4()
    uid2 = uuid4()
    await fake_workspaces.create(name="w", slug="w")
    await fake_workspaces.add_member(workspace_id=wid, user_id=uid1, role=WorkspaceRole.OWNER)
    await fake_workspaces.add_member(workspace_id=wid, user_id=uid2, role=WorkspaceRole.MEMBER)
    await fake_memories.create(
        workspace_id=wid,
        memory_type="preference",
        scope="user",
        user_id=uid1,
        content="uid1 secret",
    )
    await fake_memories.create(
        workspace_id=wid,
        memory_type="decision",
        scope="workspace",
        content="shared decision",
    )
    search = _build_search(fake_workspaces)
    svc = _build_assembly(
        fake_memories,
        fake_workspaces,
        fake_audit,
        fake_conversation,
        search,
    )
    window = await svc.assemble(workspace_id=wid, user_id=uid2, query="decision")
    assert "uid1 secret" not in [e.content for e in window.entries]
    assert any("shared decision" in e.content for e in window.entries)


@pytest.mark.asyncio
async def test_assemble_requires_query(
    fake_memories,
    fake_workspaces,
    fake_audit,
    fake_conversation,
):
    svc, wid, uid = await _seeded(
        fake_memories,
        fake_workspaces,
        fake_audit,
        fake_conversation,
    )
    with pytest.raises(ValidationError):
        await svc.assemble(workspace_id=wid, user_id=uid, query="   ")


@pytest.mark.asyncio
async def test_assemble_works_without_embeddings(
    fake_memories,
    fake_workspaces,
    fake_audit,
    fake_conversation,
):
    svc, wid, uid = await _seeded(
        fake_memories,
        fake_workspaces,
        fake_audit,
        fake_conversation,
    )
    window = await svc.assemble(workspace_id=wid, user_id=uid, query="ports")
    assert any(e.source == ContextSource.MEMORY for e in window.entries)
    assert window.truncated is False


@pytest.mark.asyncio
async def test_ranking_prefers_decision_and_scope(
    fake_memories,
    fake_workspaces,
    fake_audit,
    fake_conversation,
):
    svc, wid, uid = await _seeded(
        fake_memories,
        fake_workspaces,
        fake_audit,
        fake_conversation,
    )
    await fake_memories.create(
        workspace_id=wid,
        memory_type="preference",
        scope="workspace",
        content="prefer tabs",
        tags=["pref"],
    )
    window = await svc.assemble(workspace_id=wid, user_id=uid, query="context")
    decision = next(e for e in window.entries if e.metadata.get("memory_type") == "decision")
    preference = next(e for e in window.entries if e.metadata.get("memory_type") == "preference")
    assert decision.relevance_score > preference.relevance_score


@pytest.mark.asyncio
async def test_deduplication_by_source_and_id(
    fake_memories,
    fake_workspaces,
    fake_audit,
    fake_conversation,
):
    svc, wid, uid = await _seeded(
        fake_memories,
        fake_workspaces,
        fake_audit,
        fake_conversation,
    )
    window = await svc.assemble(workspace_id=wid, user_id=uid, query="ports")
    ids = [(e.source, e.source_id) for e in window.entries]
    assert len(ids) == len(set(ids))


@pytest.mark.asyncio
async def test_truncation_respects_max_tokens(
    fake_memories,
    fake_workspaces,
    fake_audit,
    fake_conversation,
):
    svc, wid, uid = await _seeded(
        fake_memories,
        fake_workspaces,
        fake_audit,
        fake_conversation,
    )
    for i in range(10):
        await fake_memories.create(
            workspace_id=wid,
            memory_type="fact",
            scope="workspace",
            content=f"long memory fact number {i} " + "word " * 50,
        )
    window = await svc.assemble(
        workspace_id=wid,
        user_id=uid,
        query="fact",
        max_tokens=200,
    )
    assert window.total_tokens <= 200


@pytest.mark.asyncio
async def test_scope_filter(
    fake_memories,
    fake_workspaces,
    fake_audit,
    fake_conversation,
):
    svc, wid, uid = await _seeded(
        fake_memories,
        fake_workspaces,
        fake_audit,
        fake_conversation,
    )
    window = await svc.assemble(
        workspace_id=wid,
        user_id=uid,
        query="ports",
        scope_filter=[MemoryScope.USER.value],
    )
    assert all(e.scope == MemoryScope.USER.value for e in window.entries)


@pytest.mark.asyncio
async def test_redis_failure_omits_conversation_gracefully(
    fake_memories,
    fake_workspaces,
    fake_audit,
):
    """A conversation store that raises must not fail assembly."""

    class _BrokenConversation:
        async def get(self, session_id, conversation_id):
            raise ConnectionError("redis down")

        async def append(self, *args, **kwargs):
            raise ConnectionError("redis down")

        async def clear(self, *args, **kwargs):
            raise ConnectionError("redis down")

        async def set_ttl(self, *args, **kwargs):
            raise ConnectionError("redis down")

    svc, wid, uid = await _seeded(
        fake_memories,
        fake_workspaces,
        fake_audit,
        _BrokenConversation(),
    )
    window = await svc.assemble(
        workspace_id=wid,
        user_id=uid,
        query="ports",
        session_id=uuid4(),
        conversation_id=uuid4(),
    )
    assert all(e.source != ContextSource.CONVERSATION for e in window.entries)
    assert any(e.source == ContextSource.MEMORY for e in window.entries)
