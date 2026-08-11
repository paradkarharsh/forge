"""MemoryMaintenanceService unit tests.

Covers expiration (ACTIVE -> STALE), embedding backfill (skipped when the
embedding provider is disabled), hard-delete of old soft-deleted records,
and error isolation (a failing step never aborts the run).
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from forge_api.application.memory.maintenance_service import (
    MemoryMaintenanceService,
)
from forge_api.domain.memory import MemoryStatus
from forge_api.infrastructure.embedding import NullEmbedder


class _FakeEmbedder:
    """Returns a fixed 384-dim vector for every text."""

    def dimension(self) -> int:
        return 384

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.1] * 384 for _ in texts]


def _build_service(fake_memories, embedding=None):
    return MemoryMaintenanceService(
        memories=fake_memories,
        embedding=embedding or NullEmbedder(),
        backfill_batch_size=100,
    )


@pytest.mark.asyncio
async def test_expire_marks_stale(fake_memories):
    svc = _build_service(fake_memories)
    wid = uuid4()
    expired = await fake_memories.create(
        workspace_id=wid,
        memory_type="fact",
        scope="workspace",
        content="old",
        expires_at=datetime.now(UTC) - timedelta(days=1),
    )
    fresh = await fake_memories.create(
        workspace_id=wid,
        memory_type="fact",
        scope="workspace",
        content="new",
        expires_at=datetime.now(UTC) + timedelta(days=1),
    )
    count = await svc.expire_memories()
    assert count == 1
    assert (await fake_memories.get(expired.id)).status == MemoryStatus.STALE
    assert (await fake_memories.get(fresh.id)).status == MemoryStatus.ACTIVE


@pytest.mark.asyncio
async def test_backfill_skipped_when_embeddings_disabled(fake_memories):
    svc = _build_service(fake_memories)  # NullEmbedder
    wid = uuid4()
    m = await fake_memories.create(
        workspace_id=wid,
        memory_type="fact",
        scope="workspace",
        content="x",
    )
    count = await svc.backfill_embeddings()
    assert count == 0
    assert (await fake_memories.get(m.id)).embedding is None


@pytest.mark.asyncio
async def test_backfill_embeds_missing_vectors(fake_memories):
    svc = _build_service(fake_memories, embedding=_FakeEmbedder())
    wid = uuid4()
    m1 = await fake_memories.create(
        workspace_id=wid,
        memory_type="fact",
        scope="workspace",
        content="a",
    )
    m2 = await fake_memories.create(
        workspace_id=wid,
        memory_type="fact",
        scope="workspace",
        content="b",
    )
    # Give m2 an existing embedding so only m1 is backfilled.
    await fake_memories.update(m2.id, embedding=[0.5] * 384)
    count = await svc.backfill_embeddings()
    assert count == 1
    assert len((await fake_memories.get(m1.id)).embedding) == 384


@pytest.mark.asyncio
async def test_hard_delete_only_old_soft_deleted(fake_memories):
    svc = _build_service(fake_memories)
    wid = uuid4()
    old = await fake_memories.create(
        workspace_id=wid,
        memory_type="fact",
        scope="workspace",
        content="old",
    )
    recent = await fake_memories.create(
        workspace_id=wid,
        memory_type="fact",
        scope="workspace",
        content="recent",
    )
    active = await fake_memories.create(
        workspace_id=wid,
        memory_type="fact",
        scope="workspace",
        content="active",
    )
    await fake_memories.soft_delete(old.id)
    await fake_memories.soft_delete(recent.id)

    # Backdate the old soft-delete beyond the 30-day grace period.
    m_old = fake_memories._memories[old.id]
    from forge_api.domain.memory import MemoryRecord

    fake_memories._memories[old.id] = MemoryRecord(
        id=m_old.id,
        workspace_id=m_old.workspace_id,
        repository_id=m_old.repository_id,
        user_id=m_old.user_id,
        memory_type=m_old.memory_type,
        scope=m_old.scope,
        status=m_old.status,
        content=m_old.content,
        summary=m_old.summary,
        source_file_path=m_old.source_file_path,
        source_symbol_name=m_old.source_symbol_name,
        source_commit_hash=m_old.source_commit_hash,
        confidence=m_old.confidence,
        tags=list(m_old.tags),
        embedding=m_old.embedding,
        created_by=m_old.created_by,
        created_at=m_old.created_at,
        updated_at=m_old.updated_at,
        accessed_at=m_old.accessed_at,
        expires_at=m_old.expires_at,
        deleted_at=datetime.now(UTC) - timedelta(days=31),
    )
    count = await svc.hard_delete()
    assert count == 1
    assert old.id not in fake_memories._memories  # hard-deleted
    assert recent.id in fake_memories._memories  # kept (soft-deleted, recent)
    assert active.id in fake_memories._memories  # untouched


@pytest.mark.asyncio
async def test_run_isolates_step_failures(fake_memories):
    class _BrokenMemories:
        async def find_expired(self, now, *, limit=100):
            raise RuntimeError("db down")

        async def find_missing_embeddings(self, *, limit=100):
            return []

        async def hard_delete_old(self, older_than):
            raise RuntimeError("db down")

    svc = MemoryMaintenanceService(
        memories=_BrokenMemories(),
        embedding=NullEmbedder(),
    )
    results = await svc.run()
    assert results == {"expired": 0, "backfilled": 0, "hard_deleted": 0}
