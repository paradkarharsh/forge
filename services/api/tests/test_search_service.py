"""Search service unit tests using fake repository adapters."""
from uuid import uuid4

import pytest

from forge_api.application.indexing.search_service import SearchService
from forge_api.domain.indexing import (
    ChunkRecord,
    DependencyKind,
    DependencyRecord,
    SymbolKind,
    SymbolRecord,
)
from forge_api.infrastructure.embedding import NullEmbedder


async def _seed(fake_repositories, fake_index_files, fake_symbols, fake_dependencies,
                fake_chunks):
    created = await fake_repositories.create(
        workspace_id=uuid4(),
        name="demo",
        owner="alice",
        provider="github",
        local_path="/fake",
    )
    repo_id = created.id
    file_a = await fake_index_files.upsert(
        repository_id=repo_id, path="src/app.py", language="python",
        size_bytes=10, line_count=2, commit_hash="a" * 40,
        content_hash="x",
    )
    file_b = await fake_index_files.upsert(
        repository_id=repo_id, path="src/util.py", language="python",
        size_bytes=10, line_count=2, commit_hash="a" * 40,
        content_hash="y",
    )
    await fake_symbols.bulk_create(
        [
            SymbolRecord(id=uuid4(), file_id=file_a.id, repository_id=repo_id,
                         name="add", kind=SymbolKind.FUNCTION, signature=None,
                         line_start=1, line_end=2, parent_symbol_id=None),
        ]
    )
    await fake_dependencies.bulk_create(
        [
            DependencyRecord(id=uuid4(), repository_id=repo_id,
                             source_file_id=file_b.id, target_path="src.app",
                             target_file_id=file_a.id, kind=DependencyKind.IMPORT,
                             is_external=False),
        ]
    )
    await fake_chunks.bulk_create(
        [
            ChunkRecord(id=uuid4(), file_id=file_a.id, repository_id=repo_id,
                        chunk_index=0, content="def add(): pass",
                        line_start=1, line_end=2, token_count=4,
                        embedding=[0.5] * 384),
        ]
    )
    return repo_id


def _service(fake_repositories, fake_index_files, fake_symbols, fake_dependencies,
             fake_chunks, fake_workspaces, embedding=None):
    return SearchService(
        repositories=fake_repositories,
        files=fake_index_files,
        symbols=fake_symbols,
        dependencies=fake_dependencies,
        chunks=fake_chunks,
        workspaces=fake_workspaces,
        embedding=embedding or NullEmbedder(),
    )


@pytest.mark.asyncio
async def test_search_files_by_language_and_pattern(
    fake_repositories, fake_index_files, fake_symbols, fake_dependencies,
    fake_chunks, fake_workspaces,
) -> None:
    repo_id = await _seed(fake_repositories, fake_index_files, fake_symbols,
                          fake_dependencies, fake_chunks)
    svc = _service(fake_repositories, fake_index_files, fake_symbols,
                   fake_dependencies, fake_chunks, fake_workspaces)
    python = await svc.search_files(repo_id, language="python")
    assert {f.path for f in python} == {"src/app.py", "src/util.py"}
    pattern = await svc.search_files(repo_id, pattern="src/app.py")
    assert [f.path for f in pattern] == ["src/app.py"]


@pytest.mark.asyncio
async def test_search_and_list_symbols(
    fake_repositories, fake_index_files, fake_symbols, fake_dependencies,
    fake_chunks, fake_workspaces,
) -> None:
    repo_id = await _seed(fake_repositories, fake_index_files, fake_symbols,
                          fake_dependencies, fake_chunks)
    svc = _service(fake_repositories, fake_index_files, fake_symbols,
                   fake_dependencies, fake_chunks, fake_workspaces)
    found = await svc.search_symbols(repo_id, query="add")
    assert [s.name for s in found] == ["add"]
    all_symbols = await svc.list_symbols(repo_id)
    assert len(all_symbols) == 1


@pytest.mark.asyncio
async def test_get_file_returns_symbols_and_chunks(
    fake_repositories, fake_index_files, fake_symbols, fake_dependencies,
    fake_chunks, fake_workspaces,
) -> None:
    repo_id = await _seed(fake_repositories, fake_index_files, fake_symbols,
                          fake_dependencies, fake_chunks)
    svc = _service(fake_repositories, fake_index_files, fake_symbols,
                   fake_dependencies, fake_chunks, fake_workspaces)
    data = await svc.get_file(repo_id, file_path="src/app.py")
    assert data["file"].path == "src/app.py"
    assert [s.name for s in data["symbols"]] == ["add"]
    assert len(data["chunks"]) == 1


@pytest.mark.asyncio
async def test_get_dependencies_outgoing_and_incoming(
    fake_repositories, fake_index_files, fake_symbols, fake_dependencies,
    fake_chunks, fake_workspaces,
) -> None:
    repo_id = await _seed(fake_repositories, fake_index_files, fake_symbols,
                          fake_dependencies, fake_chunks)
    svc = _service(fake_repositories, fake_index_files, fake_symbols,
                   fake_dependencies, fake_chunks, fake_workspaces)
    data = await svc.get_dependencies(repo_id, file_path="src/util.py")
    assert len(data["outgoing"]) == 1
    assert data["outgoing"][0].target_path == "src.app"
    incoming = await svc.get_dependencies(repo_id, file_path="src/app.py")
    assert len(incoming["incoming"]) == 1


@pytest.mark.asyncio
async def test_semantic_search_unavailable_without_embeddings(
    fake_repositories, fake_index_files, fake_symbols, fake_dependencies,
    fake_chunks, fake_workspaces,
) -> None:
    repo_id = await _seed(fake_repositories, fake_index_files, fake_symbols,
                          fake_dependencies, fake_chunks)
    svc = _service(fake_repositories, fake_index_files, fake_symbols,
                   fake_dependencies, fake_chunks, fake_workspaces)
    result = await svc.search_semantic(repo_id, query="something")
    assert result["available"] is False
    assert result["results"] == []


class _FakeEmbedder:
    def dimension(self) -> int | None:
        return 384

    async def embed(self, texts: list[str]) -> list[list[float] | None]:
        return [[0.1] * 384 for _ in texts]


@pytest.mark.asyncio
async def test_semantic_search_available_with_embeddings(
    fake_repositories, fake_index_files, fake_symbols, fake_dependencies,
    fake_chunks, fake_workspaces,
) -> None:
    repo_id = await _seed(fake_repositories, fake_index_files, fake_symbols,
                          fake_dependencies, fake_chunks)
    svc = _service(fake_repositories, fake_index_files, fake_symbols,
                   fake_dependencies, fake_chunks, fake_workspaces,
                   embedding=_FakeEmbedder())
    result = await svc.search_semantic(repo_id, query="add function")
    assert result["available"] is True
    assert len(result["results"]) == 1
    assert result["results"][0]["file_path"] == "src/app.py"