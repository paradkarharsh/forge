"""Repository index service unit tests.

Uses fake repository adapters, the in-memory git client, the real
tree-sitter parser and chunker, and the null embedder so the full
pipeline runs without a database or network.
"""
from uuid import uuid4

import pytest

from forge_api.application.indexing.chunking_service import ChunkingService
from forge_api.application.indexing.dependency_resolver import DependencyResolver
from forge_api.application.indexing.file_discovery_service import FileDiscoveryService
from forge_api.application.indexing.index_service import RepositoryIndexService
from forge_api.domain.errors import DomainError
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
    config: IndexingConfig = CONFIG,
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
        discovery=FileDiscoveryService(git=fake_git, max_files=config.max_files),
        config=config,
        audit=fake_audit,
    )


async def _make_repo(fake_repositories, *, local_path="/fake/repo"):
    return await fake_repositories.create(
        workspace_id=uuid4(),
        name="demo",
        owner="alice",
        provider="github",
        remote_url="https://github.com/alice/demo",
        local_path=local_path,
    )


@pytest.mark.asyncio
async def test_full_pipeline_indexes_files_symbols_deps_chunks(
    fake_repositories,
    fake_index_files,
    fake_symbols,
    fake_dependencies,
    fake_chunks,
    fake_repo_events,
    fake_workspaces,
    fake_audit,
    fake_git,
) -> None:
    fake_git.set_files(
        {
            "src/app.py": b"""import os
from pathlib import Path

def add(a, b):
    return a + b

class Foo:
    def bar(self):
        return 1
""",
            "README.md": b"just docs",
        }
    )
    svc = _build_service(
        fake_repositories, fake_index_files, fake_symbols, fake_dependencies,
        fake_chunks, fake_repo_events, fake_workspaces, fake_audit, fake_git,
    )
    repo = await _make_repo(fake_repositories)

    stats = await svc.index_repository(repo.id)

    assert stats.files_indexed == 2
    assert stats.symbols >= 3  # add, Foo, bar
    assert stats.dependencies >= 2  # os, pathlib
    assert stats.chunks >= 1
    assert stats.embeddings_created == 0

    files = await fake_index_files.list_by_repository(repo.id)
    assert {f.path for f in files} == {"src/app.py", "README.md"}

    updated = await fake_repositories.get(repo.id)
    assert updated.index_status == IndexStatus.READY
    assert updated.file_count == 2
    assert updated.symbol_count == stats.symbols

    # Audit + repository events recorded.
    assert any(e["event"] == "repository.indexed" for e in fake_audit.events)
    assert any(e.event_type == "repository.indexed" for e in fake_repo_events._events)


@pytest.mark.asyncio
async def test_content_hash_skip_avoids_re_extraction(
    fake_repositories,
    fake_index_files,
    fake_symbols,
    fake_dependencies,
    fake_chunks,
    fake_repo_events,
    fake_workspaces,
    fake_audit,
    fake_git,
) -> None:
    fake_git.set_files({"app.py": b"def f():\n    return 1\n"})
    svc = _build_service(
        fake_repositories, fake_index_files, fake_symbols, fake_dependencies,
        fake_chunks, fake_repo_events, fake_workspaces, fake_audit, fake_git,
    )
    repo = await _make_repo(fake_repositories)

    first = await svc.index_repository(repo.id)
    assert first.symbols == 1

    second = await svc.index_repository(repo.id)
    # No new symbols: the file's content hash is unchanged.
    assert second.symbols == 0
    assert second.files_indexed == 1  # metadata refreshed, not re-extracted
    symbols = await fake_symbols.list_by_repository(repo.id)
    assert len(symbols) == 1


@pytest.mark.asyncio
async def test_reindex_clears_and_reindexes(
    fake_repositories,
    fake_index_files,
    fake_symbols,
    fake_dependencies,
    fake_chunks,
    fake_repo_events,
    fake_workspaces,
    fake_audit,
    fake_git,
) -> None:
    fake_git.set_files({"a.py": b"def f():\n    return 1\n"})
    svc = _build_service(
        fake_repositories, fake_index_files, fake_symbols, fake_dependencies,
        fake_chunks, fake_repo_events, fake_workspaces, fake_audit, fake_git,
    )
    repo = await _make_repo(fake_repositories)
    await svc.index_repository(repo.id)

    fake_git.set_files({"a.py": b"def f():\n    return 1\n", "b.py": b"x = 1\n"})
    stats = await svc.reindex_repository(repo.id)
    assert stats.files_indexed == 2
    symbols = await fake_symbols.list_by_repository(repo.id)
    assert len(symbols) == 1  # only a.py has a symbol
    assert any(e["event"] == "repository.reindexed" for e in fake_audit.events)


@pytest.mark.asyncio
async def test_not_cloned_raises(
    fake_repositories,
    fake_index_files,
    fake_symbols,
    fake_dependencies,
    fake_chunks,
    fake_repo_events,
    fake_workspaces,
    fake_audit,
    fake_git,
) -> None:
    svc = _build_service(
        fake_repositories, fake_index_files, fake_symbols, fake_dependencies,
        fake_chunks, fake_repo_events, fake_workspaces, fake_audit, fake_git,
    )
    repo = await _make_repo(fake_repositories, local_path=None)
    with pytest.raises(DomainError):
        await svc.index_repository(repo.id)


@pytest.mark.asyncio
async def test_oversized_file_skipped(
    fake_repositories,
    fake_index_files,
    fake_symbols,
    fake_dependencies,
    fake_chunks,
    fake_repo_events,
    fake_workspaces,
    fake_audit,
    fake_git,
) -> None:
    fake_git.set_files({"big.py": b"x" * 5000, "small.py": b"y = 1\n"})
    svc = _build_service(
        fake_repositories, fake_index_files, fake_symbols, fake_dependencies,
        fake_chunks, fake_repo_events, fake_workspaces, fake_audit, fake_git,
        config=IndexingConfig(max_file_bytes=100, max_files=100, chunk_tokens=25,
                              chunk_overlap=0, embedding_batch_size=10, timeout_seconds=60),
    )
    repo = await _make_repo(fake_repositories)
    stats = await svc.index_repository(repo.id)
    assert stats.files_skipped == 1
    assert stats.files_indexed == 1
    files = await fake_index_files.list_by_repository(repo.id)
    assert {f.path for f in files} == {"small.py"}


@pytest.mark.asyncio
async def test_get_index_status(
    fake_repositories,
    fake_index_files,
    fake_symbols,
    fake_dependencies,
    fake_chunks,
    fake_repo_events,
    fake_workspaces,
    fake_audit,
    fake_git,
) -> None:
    fake_git.set_files({"a.py": b"def f():\n    pass\n"})
    svc = _build_service(
        fake_repositories, fake_index_files, fake_symbols, fake_dependencies,
        fake_chunks, fake_repo_events, fake_workspaces, fake_audit, fake_git,
    )
    repo = await _make_repo(fake_repositories)
    await svc.index_repository(repo.id)
    status = await svc.get_index_status(repo.id)
    assert status["index_status"] == "ready"
    assert status["file_count"] == 1
    assert status["symbol_count"] == 1


@pytest.mark.asyncio
async def test_malformed_file_does_not_abort_index(
    fake_repositories,
    fake_index_files,
    fake_symbols,
    fake_dependencies,
    fake_chunks,
    fake_repo_events,
    fake_workspaces,
    fake_audit,
    fake_git,
) -> None:
    fake_git.set_files(
        {
            "bad.py": b"def (\n)))))\n",
            "ok.py": b"def good():\n    pass\n",
        }
    )
    svc = _build_service(
        fake_repositories, fake_index_files, fake_symbols, fake_dependencies,
        fake_chunks, fake_repo_events, fake_workspaces, fake_audit, fake_git,
    )
    repo = await _make_repo(fake_repositories)
    stats = await svc.index_repository(repo.id)
    assert stats.files_indexed == 2
    # The malformed file is still stored (chunks, no symbols), the index completes.
    assert stats.symbols == 1
    assert stats.parse_errors >= 1