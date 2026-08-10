"""Repository intelligence search service.

Provides structural search (files, symbols, dependencies) that works with
no embeddings, plus semantic search over chunk embeddings when the
embedding provider is enabled. Semantic search reports availability
instead of erroring when embeddings are disabled, so structural search is
never blocked.
"""
import fnmatch

from forge_api.domain.errors import AuthorizationError, NotFoundError
from forge_api.domain.indexing import (
    DependencyRecord,
    FileRecord,
    SymbolRecord,
)
from forge_api.domain.repositories import (
    RepositoryChunkRepository,
    RepositoryDependencyRepository,
    RepositoryFileRepository,
    RepositoryRepository,
    RepositorySymbolRepository,
    WorkspaceRepository,
)
from forge_api.domain.repository import RepositoryRecord


class SearchService:
    """Queries the repository intelligence index."""

    def __init__(
        self,
        *,
        repositories: RepositoryRepository,
        files: RepositoryFileRepository,
        symbols: RepositorySymbolRepository,
        dependencies: RepositoryDependencyRepository,
        chunks: RepositoryChunkRepository,
        workspaces: WorkspaceRepository,
        embedding,
    ) -> None:
        self._repos = repositories
        self._files = files
        self._symbols = symbols
        self._deps = dependencies
        self._chunks = chunks
        self._workspaces = workspaces
        self._embedding = embedding

    async def _repo_for(self, repository_id) -> RepositoryRecord:
        repo = await self._repos.get(repository_id)
        if not repo:
            raise NotFoundError("Repository not found")
        return repo

    async def _require_member(self, workspace_id, user_id) -> None:
        member = await self._workspaces.get_membership(workspace_id, user_id)
        if not member:
            raise AuthorizationError("Not a member of this workspace")

    async def _auth(self, repository_id, user_id) -> RepositoryRecord:
        repo = await self._repo_for(repository_id)
        if user_id is not None:
            await self._require_member(repo.workspace_id, user_id)
        return repo

    async def search_files(
        self,
        repository_id,
        *,
        user_id=None,
        pattern: str | None = None,
        language: str | None = None,
        limit: int = 50,
    ) -> list[FileRecord]:
        await self._auth(repository_id, user_id)
        files = await self._files.list_by_repository(repository_id, language=language)
        if pattern is not None:
            files = [f for f in files if fnmatch.fnmatch(f.path, pattern)]
        return files[:limit]

    async def search_symbols(
        self,
        repository_id,
        *,
        user_id=None,
        query: str,
        kind: str | None = None,
        limit: int = 50,
    ) -> list[SymbolRecord]:
        await self._auth(repository_id, user_id)
        return await self._symbols.search_by_name(
            repository_id, query, kind=kind, limit=limit
        )

    async def list_symbols(
        self,
        repository_id,
        *,
        user_id=None,
        kind: str | None = None,
    ) -> list[SymbolRecord]:
        await self._auth(repository_id, user_id)
        return await self._symbols.list_by_repository(repository_id, kind=kind)

    async def get_file(self, repository_id, *, user_id=None, file_path: str) -> dict:
        await self._auth(repository_id, user_id)
        file = await self._files.get_by_path(repository_id, file_path)
        if file is None:
            raise NotFoundError("File not found in repository index")
        symbols = await self._symbols.list_by_file(file.id)
        chunks = await self._chunks.list_by_file(file.id)
        return {
            "file": file,
            "symbols": symbols,
            "chunks": chunks,
        }

    async def get_dependencies(
        self, repository_id, *, user_id=None, file_path: str
    ) -> dict:
        await self._auth(repository_id, user_id)
        file = await self._files.get_by_path(repository_id, file_path)
        if file is None:
            raise NotFoundError("File not found in repository index")
        outgoing: list[DependencyRecord] = await self._deps.list_by_file(file.id)
        incoming: list[DependencyRecord] = await self._deps.list_dependents(file.id)
        return {
            "file": file,
            "outgoing": outgoing,
            "incoming": incoming,
        }

    async def search_semantic(
        self,
        repository_id,
        *,
        user_id=None,
        query: str,
        limit: int = 20,
    ) -> dict:
        await self._auth(repository_id, user_id)
        if self._embedding.dimension() is None:
            return {"available": False, "results": []}

        vectors = await self._embedding.embed([query])
        query_embedding = vectors[0]
        if query_embedding is None:
            return {"available": False, "results": []}

        chunks = await self._chunks.search_semantic(
            repository_id, query_embedding, limit=limit
        )
        results = []
        for chunk in chunks:
            file = await self._files.get(chunk.file_id)
            results.append(
                {
                    "chunk": chunk,
                    "file_path": file.path if file else None,
                    "language": file.language if file else None,
                }
            )
        return {"available": True, "results": results}