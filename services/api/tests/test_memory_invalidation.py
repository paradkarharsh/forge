"""Post-index memory invalidation tests.

Verifies that a repository index marks stale only the memories that
explicitly reference a changed file path, that unrelated memories stay
active, and that a memory-maintenance failure never breaks indexing.
"""

from uuid import uuid4

import pytest

from forge_api.application.indexing.chunking_service import ChunkingService
from forge_api.application.indexing.dependency_resolver import DependencyResolver
from forge_api.application.indexing.file_discovery_service import FileDiscoveryService
from forge_api.application.indexing.index_service import RepositoryIndexService
from forge_api.domain.auth import WorkspaceRole
from forge_api.domain.indexing import IndexingConfig, IndexStatus
from forge_api.infrastructure.embedding import NullEmbedder
from forge_api.infrastructure.treesitter import ForgeTreeSitterParser

CONFIG = IndexingConfig(
    max_file_bytes=1024 * 1024,
    max_files=100,
    chunk_tokens=25,
    chunk_overlap=5,
    embedding_batch_size=10,
    timeout_seconds=60,
)


def _build_service(
    fake_repositories,
    fake_index_files,
    fake_symbols,
    fake_dependencies,
    fake_chunks,
    fake_repo_events,
    fake_workspaces,
    fake_audit,
    fake_git,
    fake_memories,
) -> RepositoryIndexService:
    return RepositoryIndexService(
        repositories=fake_repositories,
        files=fake_index_files,
        symbols=fake_symbols,
        dependencies=fake_dependencies,
        chunks=fake_chunks,
        events=fake_repo_events,
        workspaces=fake_workspaces,
        git=fake_git,
        parser=ForgeTreeSitterParser(),
        embedding=NullEmbedder(),
        chunker=ChunkingService(),
        resolver=DependencyResolver(),
        discovery=FileDiscoveryService(git=fake_git, max_files=100),
        config=CONFIG,
        audit=fake_audit,
        memories=fake_memories,
    )


async def _seeded_service(
    fake_repositories,
    fake_index_files,
    fake_symbols,
    fake_dependencies,
    fake_chunks,
    fake_repo_events,
    fake_workspaces,
    fake_audit,
    fake_git,
    fake_memories,
):
    wid = uuid4()
    uid = uuid4()
    await fake_workspaces.create(name="w", slug="w")
    await fake_workspaces.add_member(workspace_id=wid, user_id=uid, role=WorkspaceRole.OWNER)
    repo = await fake_repositories.create(
        workspace_id=wid,
        name="demo",
        owner="alice",
        provider="github",
        remote_url="https://x",
        local_path="/fake/repo",
    )
    fake_git.set_files(
        {
            "app.py": b"def greet(name):\n    return 'hi ' + name\n",
        }
    )
    svc = _build_service(
        fake_repositories,
        fake_index_files,
        fake_symbols,
        fake_dependencies,
        fake_chunks,
        fake_repo_events,
        fake_workspaces,
        fake_audit,
        fake_git,
        fake_memories,
    )
    return svc, wid, uid, repo


@pytest.mark.asyncio
async def test_reindex_marks_only_linked_memories_stale(
    fake_repositories,
    fake_index_files,
    fake_symbols,
    fake_dependencies,
    fake_chunks,
    fake_repo_events,
    fake_workspaces,
    fake_audit,
    fake_git,
    fake_memories,
):
    svc, wid, uid, repo = await _seeded_service(
        fake_repositories,
        fake_index_files,
        fake_symbols,
        fake_dependencies,
        fake_chunks,
        fake_repo_events,
        fake_workspaces,
        fake_audit,
        fake_git,
        fake_memories,
    )
    # Initial index.
    await svc.index_repository(repo.id, user_id=uid)

    # Memory linked to app.py and an unrelated workspace memory.
    linked = await fake_memories.create(
        workspace_id=wid,
        repository_id=repo.id,
        memory_type="annotation",
        scope="repository",
        content="notes on greet",
        source_file_path="app.py",
    )
    unrelated = await fake_memories.create(
        workspace_id=wid,
        memory_type="decision",
        scope="workspace",
        content="use ports",
    )

    # Change app.py content.
    fake_git.set_files(
        {
            "app.py": b"def greet(name):\n    return 'HELLO ' + name\n",
        }
    )
    await svc.reindex_repository(repo.id, user_id=uid)

    assert (await fake_memories.get(linked.id)).status.value == "stale"
    assert (await fake_memories.get(unrelated.id)).status.value == "active"


@pytest.mark.asyncio
async def test_reindex_without_change_keeps_memories_active(
    fake_repositories,
    fake_index_files,
    fake_symbols,
    fake_dependencies,
    fake_chunks,
    fake_repo_events,
    fake_workspaces,
    fake_audit,
    fake_git,
    fake_memories,
):
    svc, wid, uid, repo = await _seeded_service(
        fake_repositories,
        fake_index_files,
        fake_symbols,
        fake_dependencies,
        fake_chunks,
        fake_repo_events,
        fake_workspaces,
        fake_audit,
        fake_git,
        fake_memories,
    )
    await svc.index_repository(repo.id, user_id=uid)
    linked = await fake_memories.create(
        workspace_id=wid,
        repository_id=repo.id,
        memory_type="annotation",
        scope="repository",
        content="notes",
        source_file_path="app.py",
    )
    # No content change on the second index run.
    await svc.index_repository(repo.id, user_id=uid)
    assert (await fake_memories.get(linked.id)).status.value == "active"


@pytest.mark.asyncio
async def test_indexing_succeeds_even_if_memory_invalidation_fails(
    fake_repositories,
    fake_index_files,
    fake_symbols,
    fake_dependencies,
    fake_chunks,
    fake_repo_events,
    fake_workspaces,
    fake_audit,
    fake_git,
):
    """A failing memory store must not break repository indexing."""

    class _BrokenMemories:
        async def list_by_repository(self, repository_id, **kwargs):
            raise RuntimeError("memory db down")

        async def mark_stale(self, repository_id, paths):
            raise RuntimeError("memory db down")

    svc, wid, uid, repo = await _seeded_service(
        fake_repositories,
        fake_index_files,
        fake_symbols,
        fake_dependencies,
        fake_chunks,
        fake_repo_events,
        fake_workspaces,
        fake_audit,
        fake_git,
        _BrokenMemories(),
    )
    stats = await svc.index_repository(repo.id, user_id=uid)
    assert stats.files_indexed == 1
    assert (await fake_repositories.get(repo.id)).index_status == IndexStatus.READY
