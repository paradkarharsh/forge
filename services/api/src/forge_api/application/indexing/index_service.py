"""Repository indexing orchestration service.

Coordinates the full pipeline for one repository: discover files via the
git port, read file contents, parse with tree-sitter, resolve
dependencies, chunk, optionally embed, and persist files / symbols /
dependencies / chunks through the repository ports. The service is an
orchestrator only — all I/O and parsing is delegated to ports so each
concern stays independently testable.
"""
import hashlib
import logging
from dataclasses import replace
from datetime import UTC, datetime
from time import monotonic
from uuid import UUID, uuid4

from forge_api.domain.audit import AuditEventType
from forge_api.domain.errors import AuthorizationError, DomainError, NotFoundError
from forge_api.domain.indexing import (
    Chunk,
    ChunkRecord,
    DependencyRecord,
    GitClient,
    IndexingConfig,
    IndexStats,
    ParsedSymbol,
    ParseResult,
    SymbolRecord,
    TreeSitterParser,
)
from forge_api.domain.repositories import (
    MemoryRepository,
    RepositoryChunkRepository,
    RepositoryDependencyRepository,
    RepositoryEventRepository,
    RepositoryFileRepository,
    RepositoryRepository,
    RepositorySymbolRepository,
    WorkspaceRepository,
)
from forge_api.domain.repository import RepositoryRecord
from forge_api.infrastructure.audit import AuditLogger

logger = logging.getLogger(__name__)

_INDEX_ROLES = frozenset({"owner", "admin", "maintainer"})


class RepositoryIndexService:
    """Orchestrates repository indexing end to end."""

    def __init__(
        self,
        *,
        repositories: RepositoryRepository,
        files: RepositoryFileRepository,
        symbols: RepositorySymbolRepository,
        dependencies: RepositoryDependencyRepository,
        chunks: RepositoryChunkRepository,
        events: RepositoryEventRepository,
        workspaces: WorkspaceRepository,
        git: GitClient,
        parser: TreeSitterParser,
        embedding,
        chunker,
        resolver,
        discovery,
        config: IndexingConfig,
        audit: AuditLogger,
        memories: MemoryRepository | None = None,
    ) -> None:
        self._repos = repositories
        self._files = files
        self._symbols = symbols
        self._deps = dependencies
        self._chunks = chunks
        self._events = events
        self._workspaces = workspaces
        self._git = git
        self._parser = parser
        self._embedding = embedding
        self._chunker = chunker
        self._resolver = resolver
        self._discovery = discovery
        self._config = config
        self._audit = audit
        self._memories = memories

    async def _require_index_role(self, workspace_id: UUID, user_id: UUID) -> None:
        member = await self._workspaces.get_membership(workspace_id, user_id)
        if not member:
            raise AuthorizationError("Not a member of this workspace")
        if member.role.value not in _INDEX_ROLES:
            raise AuthorizationError("Insufficient workspace role")

    async def _require_member(self, workspace_id: UUID, user_id: UUID) -> None:
        member = await self._workspaces.get_membership(workspace_id, user_id)
        if not member:
            raise AuthorizationError("Not a member of this workspace")

    async def index_repository(
        self, repository_id: UUID, *, user_id: UUID | None = None
    ) -> IndexStats:
        """Run a full index of the repository's HEAD revision."""
        repo = await self._repos.get(repository_id)
        if not repo:
            raise NotFoundError("Repository not found")
        if user_id is not None:
            await self._require_index_role(repo.workspace_id, user_id)
        if not repo.local_path:
            raise DomainError(
                "Repository is not cloned; nothing to index", code="not_cloned"
            )

        start = monotonic()
        head = await self._git.head_revision(repo.local_path)
        discovered = await self._discovery.discover_files(repo.local_path, head)
        files_set = {f.path for f in discovered}
        stats, changed_paths = await self._index_files(
            repo, head, discovered, files_set, start
        )
        await self._complete(
            repo, stats, user_id, reindexed=False, changed_paths=changed_paths
        )
        return stats

    async def reindex_repository(
        self, repository_id: UUID, *, user_id: UUID | None = None
    ) -> IndexStats:
        """Drop all indexed data for the repository, then index from scratch."""
        repo = await self._repos.get(repository_id)
        if not repo:
            raise NotFoundError("Repository not found")
        if user_id is not None:
            await self._require_index_role(repo.workspace_id, user_id)

        # Capture repository-scoped memory source paths before the drop so
        # file-linked memories can be marked stale after the reindex.
        stale_candidates: list[str] = []
        if self._memories is not None:
            try:
                repo_memories = await self._memories.list_by_repository(
                    repository_id, status="active"
                )
                stale_candidates = [
                    m.source_file_path
                    for m in repo_memories
                    if m.source_file_path
                ]
            except Exception:
                logger.warning(
                    "Failed to collect memory paths before reindex %s",
                    repository_id,
                )

        await self._chunks.delete_by_repository(repository_id)
        await self._deps.delete_by_repository(repository_id)
        await self._symbols.delete_by_repository(repository_id)
        await self._files.delete_by_repository(repository_id)

        stats = await self.index_repository(repository_id, user_id=user_id)
        await self._complete(
            repo,
            stats,
            user_id,
            reindexed=True,
            changed_paths=stale_candidates,
        )
        return stats
    async def get_index_status(
        self, repository_id: UUID, *, user_id: UUID | None = None
    ) -> dict:
        """Return the repository's current index status and counts."""
        repo = await self._repos.get(repository_id)
        if not repo:
            raise NotFoundError("Repository not found")
        if user_id is not None:
            await self._require_member(repo.workspace_id, user_id)

        return {
            "repository_id": str(repo.id),
            "index_status": repo.index_status.value,
            "indexed_at": repo.indexed_at.isoformat() if repo.indexed_at else None,
            "file_count": repo.file_count,
            "symbol_count": repo.symbol_count,
        }

    async def _index_files(
        self,
        repo: RepositoryRecord,
        head: str,
        discovered: list,
        files_set: set[str],
        start: float,
    ) -> tuple[IndexStats, list[str]]:
        indexed = skipped = symbol_total = dep_total = chunk_total = 0
        emb_total = parse_errors = 0
        changed_paths: list[str] = []
        path_to_id: dict[str, UUID] = {}
        pending_deps: list[tuple[DependencyRecord, str | None]] = []

        for df in discovered:
            if monotonic() - start > self._config.timeout_seconds:
                raise DomainError("Indexing timed out", code="index_timeout")

            if df.size_bytes is not None and df.size_bytes > self._config.max_file_bytes:
                skipped += 1
                continue

            raw = await self._safe_read(repo, head, df.path)
            if raw is None:
                parse_errors += 1
                continue

            content_hash = hashlib.sha256(raw).hexdigest()
            existing = await self._files.get_by_path(repo.id, df.path)
            if existing is not None and existing.content_hash == content_hash:
                # Content unchanged: refresh metadata, keep old artifacts.
                await self._files.upsert(
                    repository_id=repo.id,
                    path=df.path,
                    language=df.language,
                    size_bytes=df.size_bytes or len(raw),
                    line_count=existing.line_count,
                    commit_hash=head,
                    content_hash=content_hash,
                )
                path_to_id[df.path] = existing.id
                indexed += 1
                continue

            # Content changed (or file is new): record the path so linked
            # memories can be invalidated after a successful index.
            if existing is not None:
                changed_paths.append(df.path)

            text = raw.decode("utf-8", errors="replace")
            parsed = (
                self._parser.parse(text, df.language)
                if df.language is not None
                else ParseResult((), ())
            )
            parse_errors += len(parsed.errors)

            # Remove stale artifacts from a previous index of this file.
            if existing is not None:
                await self._symbols.delete_by_file(existing.id)
                await self._deps.delete_by_file(existing.id)
                await self._chunks.delete_by_file(existing.id)

            file_rec = await self._files.upsert(
                repository_id=repo.id,
                path=df.path,
                language=df.language,
                size_bytes=df.size_bytes or len(raw),
                line_count=len(text.splitlines()),
                commit_hash=head,
                content_hash=content_hash,
            )
            path_to_id[file_rec.path] = file_rec.id

            symbol_records = self._flatten_symbols(repo.id, file_rec.id, parsed.symbols)
            await self._symbols.bulk_create(symbol_records)

            file_deps, resolved = self._build_dependencies(
                repo.id, file_rec.id, df.path, parsed.dependencies, files_set, df.language
            )
            pending_deps.extend(zip(file_deps, resolved, strict=False))

            chunks = self._chunker.chunk_file(
                content=text,
                symbols=list(parsed.symbols),
                chunk_tokens=self._config.chunk_tokens,
                overlap_tokens=self._config.chunk_overlap,
            )
            chunk_records = self._build_chunks(repo.id, file_rec.id, chunks)
            if self._embedding.dimension() is not None:
                chunk_records, emb_created = await self._embed_chunks(chunk_records)
                emb_total += emb_created
            await self._chunks.bulk_create(chunk_records)

            indexed += 1
            symbol_total += len(symbol_records)
            dep_total += len(file_deps)
            chunk_total += len(chunk_records)

        await self._persist_dependencies(pending_deps, path_to_id)
        return (
            IndexStats(
                files_indexed=indexed,
                files_skipped=skipped,
                symbols=symbol_total,
                dependencies=dep_total,
                chunks=chunk_total,
                embeddings_created=emb_total,
                parse_errors=parse_errors,
            ),
            changed_paths,
        )

    async def _safe_read(self, repo: RepositoryRecord, head: str, path: str) -> bytes | None:
        try:
            return await self._git.read_file(repo.local_path, head, path)
        except DomainError:
            logger.warning("Failed to read %s in %s", path, repo.id)
            return None

    def _flatten_symbols(
        self, repository_id: UUID, file_id: UUID, symbols: list[ParsedSymbol]
    ) -> list[SymbolRecord]:
        records: list[SymbolRecord] = []

        def visit(items: list[ParsedSymbol], parent_id: UUID | None) -> None:
            for sym in items:
                sid = uuid4()
                records.append(
                    SymbolRecord(
                        id=sid,
                        file_id=file_id,
                        repository_id=repository_id,
                        name=sym.name,
                        kind=sym.kind,
                        signature=sym.signature,
                        line_start=sym.line_start,
                        line_end=sym.line_end,
                        parent_symbol_id=parent_id,
                    )
                )
                visit(list(sym.children), sid)

        visit(symbols, None)
        return records

    def _build_dependencies(
        self,
        repository_id: UUID,
        source_file_id: UUID,
        source_path: str,
        parsed_deps,
        files_set: set[str],
        language: str | None,
    ) -> tuple[list[DependencyRecord], list[str | None]]:
        records: list[DependencyRecord] = []
        resolved_paths: list[str | None] = []
        for dep in parsed_deps:
            resolved, external = self._resolver.resolve(
                source_path=source_path,
                target_path=dep.target_path,
                repo_files=files_set,
                language=language,
            )
            records.append(
                DependencyRecord(
                    id=uuid4(),
                    repository_id=repository_id,
                    source_file_id=source_file_id,
                    target_path=dep.target_path,
                    target_file_id=None,
                    kind=dep.kind,
                    is_external=external,
                )
            )
            resolved_paths.append(resolved)
        return records, resolved_paths

    def _build_chunks(
        self, repository_id: UUID, file_id: UUID, chunks: list[Chunk]
    ) -> list[ChunkRecord]:
        records = []
        for index, chunk in enumerate(chunks):
            records.append(
                ChunkRecord(
                    id=uuid4(),
                    file_id=file_id,
                    repository_id=repository_id,
                    chunk_index=index,
                    content=chunk.content,
                    line_start=chunk.line_start,
                    line_end=chunk.line_end,
                    token_count=chunk.token_count,
                )
            )
        return records

    async def _embed_chunks(
        self, chunk_records: list[ChunkRecord]
    ) -> tuple[list[ChunkRecord], int]:
        batch_size = self._config.embedding_batch_size
        updated: list[ChunkRecord] = []
        created = 0
        for start in range(0, len(chunk_records), batch_size):
            batch = chunk_records[start : start + batch_size]
            vectors = await self._embedding.embed([c.content for c in batch])
            for chunk, vector in zip(batch, vectors, strict=False):
                if vector is not None:
                    chunk = replace(chunk, embedding=list(vector))
                    created += 1
                updated.append(chunk)
        return updated, created

    async def _persist_dependencies(
        self,
        pending: list[tuple[DependencyRecord, str | None]],
        path_to_id: dict[str, UUID],
    ) -> None:
        if not pending:
            return
        final: list[DependencyRecord] = []
        for record, resolved_path in pending:
            if (
                not record.is_external
                and resolved_path is not None
                and resolved_path in path_to_id
            ):
                record = replace(record, target_file_id=path_to_id[resolved_path])
            final.append(record)
        await self._deps.bulk_create(final)

    async def _complete(
        self,
        repo: RepositoryRecord,
        stats: IndexStats,
        user_id: UUID | None,
        *,
        reindexed: bool,
        changed_paths: list[str] | None = None,
    ) -> None:
        now = datetime.now(UTC)
        await self._repos.update(
            repo.id,
            index_status="ready",
            indexed_at=now,
            file_count=stats.files_indexed,
            symbol_count=stats.symbols,
        )
        event_type = (
            AuditEventType.REPOSITORY_REINDEXED
            if reindexed
            else AuditEventType.REPOSITORY_INDEXED
        )
        payload = {
            "files": stats.files_indexed,
            "symbols": stats.symbols,
            "dependencies": stats.dependencies,
            "chunks": stats.chunks,
            "embeddings": stats.embeddings_created,
        }
        self._audit.log(event_type, user_id=user_id, payload=payload)
        await self._events.create(
            repository_id=repo.id,
            event_type=event_type.value,
            actor_id=user_id,
            payload=payload,
        )

        # Post-index memory invalidation: mark stale only memories that
        # explicitly reference a changed file path.  Memories without
        # source linkage remain active.  A memory failure here must never
        # fail repository indexing.
        if changed_paths and self._memories is not None:
            try:
                count = await self._memories.mark_stale(repo.id, changed_paths)
                if count:
                    self._audit.log(
                        AuditEventType.MEMORY_STALE_MARKED,
                        user_id=user_id,
                        payload={
                            "repository_id": str(repo.id),
                            "memory_count": count,
                            "changed_paths": len(changed_paths),
                        },
                    )
            except Exception:
                logger.exception(
                    "Memory invalidation failed after indexing repository %s",
                    repo.id,
                )