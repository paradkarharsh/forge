"""Context retrieval and assembly service.

Combines structural and semantic retrieval into a ranked, deduplicated,
truncated context window ready for a future LLM consumer.  Structural
retrieval (memory tags/types, repository symbols/files/dependencies,
conversation context) always works; semantic retrieval (memory vectors,
repository chunk vectors) runs only when embeddings are available and
degrades gracefully otherwise.  A missing embedding provider never makes
assembly fail.
"""
import logging
from datetime import UTC, datetime
from uuid import UUID

from forge_api.application.indexing.chunking_service import count_tokens
from forge_api.application.indexing.search_service import SearchService
from forge_api.domain.audit import AuditEventType
from forge_api.domain.errors import AuthorizationError, ValidationError
from forge_api.domain.memory import (
    ContextEntry,
    ContextRankingConfig,
    ContextSource,
    ContextWindow,
    MemoryRecord,
    MemoryScope,
    MemoryType,
)
from forge_api.domain.repositories import (
    ConversationContextStore,
    MemoryRepository,
    WorkspaceRepository,
)
from forge_api.infrastructure.audit import AuditLogger

logger = logging.getLogger(__name__)

# Type priority for ranking: higher value = higher relevance at equal score.
_TYPE_PRIORITY = {
    MemoryType.DECISION: 1.0,
    MemoryType.CONVENTION: 0.9,
    MemoryType.FACT: 0.8,
    MemoryType.ANNOTATION: 0.7,
    MemoryType.SUMMARY: 0.6,
    MemoryType.PREFERENCE: 0.5,
}

_RECENCY_HALF_LIFE_DAYS = 30.0


class ContextAssemblyService:
    """Assembles a context window from memory + repository intelligence."""

    def __init__(
        self,
        *,
        memories: MemoryRepository,
        search: SearchService,
        conversation: ConversationContextStore,
        embedding,
        workspaces: WorkspaceRepository,
        audit: AuditLogger,
        ranking: ContextRankingConfig,
        max_tokens: int = 8192,
        min_relevance: float = 0.1,
        conversation_max_entries: int = 100,
    ) -> None:
        self._memories = memories
        self._search = search
        self._conversation = conversation
        self._embedding = embedding
        self._workspaces = workspaces
        self._audit = audit
        self._ranking = ranking
        self._max_tokens = max_tokens
        self._min_relevance = min_relevance
        self._conversation_max_entries = conversation_max_entries

    async def assemble(
        self,
        *,
        workspace_id: UUID,
        user_id: UUID,
        query: str,
        repository_id: UUID | None = None,
        session_id: UUID | None = None,
        conversation_id: UUID | None = None,
        max_tokens: int | None = None,
        scope_filter: list[str] | None = None,
        type_filter: list[str] | None = None,
    ) -> ContextWindow:
        query = (query or "").strip()
        if not query:
            raise ValidationError("query is required")
        if len(query) > 512:
            raise ValidationError("query exceeds maximum length of 512")

        member = await self._workspaces.get_membership(workspace_id, user_id)
        if not member:
            raise AuthorizationError("Not a member of this workspace")

        token_budget = max_tokens or self._max_tokens
        assembled_at = datetime.now(UTC)

        entries = await self._retrieve(
            workspace_id=workspace_id,
            user_id=user_id,
            query=query,
            repository_id=repository_id,
            session_id=session_id,
            conversation_id=conversation_id,
            scope_filter=scope_filter,
            type_filter=type_filter,
        )

        # Normalize + deduplicate + rank + filter + truncate.
        ranked = self._rank(entries)
        window_entries = self._truncate(ranked, token_budget)

        # Touch accessed_at for the memories that made it into the window.
        memory_ids = [
            e.source_id
            for e in window_entries
            if e.source == ContextSource.MEMORY and e.source_id is not None
        ]
        if memory_ids:
            try:
                await self._memories.touch_accessed(memory_ids)
            except Exception:
                logger.warning("Failed to update memory accessed_at")

        self._audit.log(
            AuditEventType.CONTEXT_ASSEMBLED,
            user_id=user_id,
            payload={
                "workspace_id": str(workspace_id),
                "repository_id": str(repository_id) if repository_id else None,
                "query": query[:256],
                "entries_count": len(window_entries),
                "total_tokens": sum(
                    count_tokens(e.content) for e in window_entries
                ),
                "truncated": len(entries) > len(window_entries),
            },
        )

        return ContextWindow(
            entries=tuple(window_entries),
            total_tokens=sum(count_tokens(e.content) for e in window_entries),
            truncated=len(entries) > len(window_entries),
            repository_id=repository_id,
            workspace_id=workspace_id,
            assembled_at=assembled_at,
        )

    # ─── Retrieval fan-out ──────────────────────────────────────────

    async def _retrieve(
        self,
        *,
        workspace_id: UUID,
        user_id: UUID,
        query: str,
        repository_id: UUID | None,
        session_id: UUID | None,
        conversation_id: UUID | None,
        scope_filter: list[str] | None,
        type_filter: list[str] | None,
    ) -> list[ContextEntry]:
        # Retrieval branches run sequentially on the shared request-scoped
        # AsyncSession.  SQLAlchemy async sessions are not safe for
        # concurrent IO, so parallel fan-out is deferred until each branch
        # gets its own session.  Each branch still isolates its own errors.
        coroutines: list = [
            self._retrieve_memories(
                workspace_id, user_id, repository_id,
                scope_filter, type_filter,
            )
        ]

        # Structural: repository intelligence (only for repository context).
        if repository_id is not None:
            coroutines.append(
                self._retrieve_repository_intelligence(
                    repository_id, user_id, query,
                )
            )

        # Structural: conversation context (ephemeral).
        if session_id is not None and conversation_id is not None:
            coroutines.append(
                self._retrieve_conversation(session_id, conversation_id)
            )

        # Semantic: memory vectors + repository chunk vectors.
        coroutines.extend(
            self._retrieve_semantic(
                workspace_id, user_id, repository_id, query,
            )
        )

        entries: list[ContextEntry] = []
        for coro in coroutines:
            try:
                result = await coro
            except Exception:
                logger.warning(
                    "Context retrieval branch failed", exc_info=True
                )
                continue
            if result:
                entries.extend(result)
        return entries

    async def _retrieve_memories(
        self,
        workspace_id: UUID,
        user_id: UUID,
        repository_id: UUID | None,
        scope_filter: list[str] | None,
        type_filter: list[str] | None,
    ) -> list[ContextEntry]:
        memory_type = type_filter[0] if type_filter and len(type_filter) == 1 else None
        records: list[MemoryRecord] = []

        # Repository context includes both the repository-scoped memories
        # and the workspace-level memories that apply project-wide.
        if repository_id is not None:
            records.extend(
                await self._memories.list_by_repository(
                    repository_id,
                    memory_type=memory_type,
                    status="active",
                    limit=50,
                )
            )
            workspace_records = await self._memories.list_by_workspace(
                workspace_id,
                memory_type=memory_type,
                status="active",
                limit=50,
            )
            seen = {m.id for m in records}
            records.extend(m for m in workspace_records if m.id not in seen)
        else:
            records = await self._memories.list_by_workspace(
                workspace_id,
                memory_type=memory_type,
                status="active",
                limit=50,
            )

        entries: list[ContextEntry] = []
        for m in records:
            if scope_filter and m.scope not in scope_filter:
                continue
            if type_filter and m.memory_type not in type_filter:
                continue
            if m.scope == MemoryScope.USER.value and m.user_id != user_id:
                continue
            entries.append(self._memory_entry(m))
        return entries

    async def _retrieve_repository_intelligence(
        self, repository_id: UUID, user_id: UUID, query: str,
    ) -> list[ContextEntry]:
        entries: list[ContextEntry] = []

        # Symbols matching the query.
        try:
            symbols = await self._search.search_symbols(
                repository_id, user_id=user_id, query=query, limit=10,
            )
            for sym in symbols:
                entries.append(
                    ContextEntry(
                        source=ContextSource.REPOSITORY_SYMBOL,
                        scope=MemoryScope.REPOSITORY,
                        content=sym.signature or sym.name,
                        relevance_score=0.0,  # set during ranking
                        source_id=sym.id,
                        file_path=None,
                        metadata={
                            "name": sym.name,
                            "kind": sym.kind.value,
                            "line_start": sym.line_start,
                        },
                    )
                )
        except Exception:
            logger.warning("Symbol retrieval failed during assembly")

        # Files matching the query pattern.
        try:
            files = await self._search.search_files(
                repository_id, user_id=user_id, pattern=query, limit=5,
            )
            for f in files:
                entries.append(
                    ContextEntry(
                        source=ContextSource.REPOSITORY_FILE,
                        scope=MemoryScope.REPOSITORY,
                        content=f.path,
                        relevance_score=0.0,
                        source_id=f.id,
                        file_path=f.path,
                        metadata={"language": f.language},
                    )
                )
                # Dependency information for the matched file.
                try:
                    dep_info = await self._search.get_dependencies(
                        repository_id, user_id=user_id, file_path=f.path,
                    )
                    outgoing = dep_info["outgoing"][:10]
                    for dep in outgoing:
                        entries.append(
                            ContextEntry(
                                source=ContextSource.REPOSITORY_DEPENDENCY,
                                scope=MemoryScope.REPOSITORY,
                                content=f"{f.path} -> {dep.target_path}",
                                relevance_score=0.0,
                                source_id=dep.id,
                                file_path=f.path,
                                metadata={
                                    "target_path": dep.target_path,
                                    "kind": dep.kind.value,
                                    "is_external": dep.is_external,
                                },
                            )
                        )
                except Exception:
                    pass
        except Exception:
            logger.warning("File retrieval failed during assembly")

        return entries

    async def _retrieve_conversation(
        self, session_id: UUID, conversation_id: UUID,
    ) -> list[ContextEntry]:
        try:
            records = await self._conversation.get(session_id, conversation_id)
        except Exception:
            return []
        # Only the most recent entries participate.
        records = records[-self._conversation_max_entries :]
        return [
            ContextEntry(
                source=ContextSource.CONVERSATION,
                scope=MemoryScope.USER,
                content=entry.content,
                relevance_score=0.5,
                source_id=None,
                file_path=None,
                metadata={"role": entry.role},
            )
            for entry in records
        ]

    def _retrieve_semantic(
        self,
        workspace_id: UUID,
        user_id: UUID,
        repository_id: UUID | None,
        query: str,
    ) -> list:
        """Return semantic retrieval coroutines; empty list when embeddings absent."""
        if self._embedding.dimension() is None:
            return []

        async def _embed_and_search():
            vectors = await self._embedding.embed([query])
            query_embedding = vectors[0]
            if query_embedding is None:
                return []
            entries: list[ContextEntry] = []

            # Memory vectors (workspace + optional repository scope).
            memories = await self._memories.search_semantic(
                workspace_id,
                query_embedding,
                repository_id=repository_id,
                user_id=None,
                limit=10,
            )
            entries.extend(self._memory_entry(m) for m in memories)

            # Repository chunk vectors.
            if repository_id is not None:
                try:
                    chunk_results = await self._search.search_semantic(
                        repository_id,
                        user_id=user_id,
                        query=query,
                        limit=10,
                    )
                    for item in chunk_results["results"]:
                        chunk = item["chunk"]
                        entries.append(
                            ContextEntry(
                                source=ContextSource.REPOSITORY_CHUNK,
                                scope=MemoryScope.REPOSITORY,
                                content=chunk.content,
                                relevance_score=0.0,
                                source_id=chunk.id,
                                file_path=item["file_path"],
                                metadata={
                                    "language": item["language"],
                                    "chunk_index": chunk.chunk_index,
                                },
                            )
                        )
                except Exception:
                    logger.warning("Chunk semantic search failed during assembly")
            return entries

        return [_embed_and_search()]

    # ─── Normalize / rank / filter / truncate ───────────────────────

    def _memory_entry(self, m: MemoryRecord) -> ContextEntry:
        return ContextEntry(
            source=ContextSource.MEMORY,
            scope=m.scope,
            content=m.content,
            relevance_score=0.0,  # set during ranking
            source_id=m.id,
            file_path=m.source_file_path,
            metadata={
                "memory_type": m.memory_type,
                "summary": m.summary,
                "confidence": m.confidence,
                "tags": list(m.tags),
                "status": m.status.value,
                "updated_at": m.updated_at,
            },
        )

    def _rank(self, entries: list[ContextEntry]) -> list[ContextEntry]:
        """Compute a relevance score for each entry and sort descending."""
        scored: list[ContextEntry] = []
        for e in entries:
            score = self._score(e)
            scored.append(
                ContextEntry(
                    source=e.source,
                    scope=e.scope,
                    content=e.content,
                    relevance_score=score,
                    source_id=e.source_id,
                    file_path=e.file_path,
                    metadata=e.metadata,
                )
            )
        # Deduplicate by (source, source_id) keeping the highest score.
        dedup: dict[tuple, ContextEntry] = {}
        for e in scored:
            key = (e.source, e.source_id)
            if key in dedup:
                if e.relevance_score > dedup[key].relevance_score:
                    dedup[key] = e
            else:
                dedup[key] = e
        ranked = list(dedup.values())
        ranked.sort(key=lambda e: e.relevance_score, reverse=True)
        return ranked

    def _score(self, e: ContextEntry) -> float:
        r = self._ranking
        semantic = self._semantic_score(e)
        recency = self._recency_score(e)
        confidence = self._confidence_score(e)
        scope = self._scope_score(e)
        type_priority = self._type_score(e)
        return (
            r.semantic_weight * semantic
            + r.recency_weight * recency
            + r.confidence_weight * confidence
            + r.scope_weight * scope
            + r.type_weight * type_priority
        )

    def _semantic_score(self, e: ContextEntry) -> float:
        # Semantic chunk entries carry their raw cosine similarity on the
        # relevance field; memory semantic entries re-score by recency/scope.
        if e.source == ContextSource.REPOSITORY_CHUNK:
            return e.relevance_score
        return 0.0

    def _recency_score(self, e: ContextEntry) -> float:
        # Newer entries score higher (exponential decay over a half life).
        updated_at = e.metadata.get("updated_at")
        if not isinstance(updated_at, datetime):
            return 0.5
        delta_days = (datetime.now(UTC) - updated_at).total_seconds() / 86_400
        return max(0.0, 1.0 - min(1.0, delta_days / _RECENCY_HALF_LIFE_DAYS))

    def _confidence_score(self, e: ContextEntry) -> float:
        conf = e.metadata.get("confidence")
        if conf is None:
            return 1.0
        try:
            return float(conf)
        except (TypeError, ValueError):
            return 1.0

    def _scope_score(self, e: ContextEntry) -> float:
        # Repository-scoped entries score highest for repository queries;
        # workspace entries slightly lower; user entries baseline.
        if e.scope == MemoryScope.REPOSITORY.value:
            return 1.0
        if e.scope == MemoryScope.WORKSPACE.value:
            return 0.8
        return 0.5

    def _type_score(self, e: ContextEntry) -> float:
        if e.source == ContextSource.MEMORY:
            mtype = e.metadata.get("memory_type")
            try:
                return _TYPE_PRIORITY.get(MemoryType(mtype), 0.5)
            except (ValueError, TypeError):
                return 0.5
        return 0.5

    def _truncate(
        self, ranked: list[ContextEntry], max_tokens: int,
    ) -> list[ContextEntry]:
        selected: list[ContextEntry] = []
        total = 0
        for e in ranked:
            if e.relevance_score < self._min_relevance:
                continue
            tokens = count_tokens(e.content)
            if total + tokens > max_tokens:
                break
            selected.append(e)
            total += tokens
        return selected
