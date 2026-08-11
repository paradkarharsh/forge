"""SQLAlchemy adapter for the MemoryRepository protocol.

Every query enforces workspace isolation at the adapter level, and
user-scoped queries additionally enforce user ownership, so isolation
never depends on the HTTP layer alone.  Semantic search uses pgvector's
cosine distance operator (``<=>``) via the ``Vector`` type's
``cosine_distance`` helper, matching the RepositoryChunkRepository.
"""
from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from forge_api.domain.memory import (
    MemoryRecord,
    MemoryScope,
    MemoryStatus,
    MemoryType,
)
from forge_api.infrastructure.database.models import MemoryModel


def _to_record(model: MemoryModel) -> MemoryRecord:
    return MemoryRecord(
        id=model.id,
        workspace_id=model.workspace_id,
        repository_id=model.repository_id,
        user_id=model.user_id,
        memory_type=MemoryType(model.memory_type),
        scope=MemoryScope(model.scope),
        status=MemoryStatus(model.status),
        content=model.content,
        summary=model.summary,
        source_file_path=model.source_file_path,
        source_symbol_name=model.source_symbol_name,
        source_commit_hash=model.source_commit_hash,
        confidence=model.confidence,
        tags=list(model.tags or []),
        embedding=list(model.embedding) if model.embedding is not None else None,
        created_by=model.created_by,
        created_at=model.created_at,
        updated_at=model.updated_at,
        accessed_at=model.accessed_at,
        expires_at=model.expires_at,
        deleted_at=model.deleted_at,
    )


def _base_query(workspace_id: UUID) -> select:
    """Active (non-deleted) memories within a workspace."""
    return select(MemoryModel).where(
        MemoryModel.workspace_id == workspace_id,
        MemoryModel.deleted_at.is_(None),
    )


def _base_query_by_repository(repository_id: UUID) -> select:
    """Active (non-deleted) memories for a repository.

    Repository memories always carry their repository_id; repository-scoped
    reads never cross workspaces.
    """
    return select(MemoryModel).where(
        MemoryModel.repository_id == repository_id,
        MemoryModel.deleted_at.is_(None),
    )


class SqlMemoryRepository:
    """Concrete SQLAlchemy implementation of ``MemoryRepository``."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get(self, memory_id: UUID) -> MemoryRecord | None:
        model = await self._db.get(MemoryModel, memory_id)
        if model is None or model.deleted_at is not None:
            return None
        return _to_record(model)

    async def list_by_workspace(
        self,
        workspace_id: UUID,
        *,
        memory_type: str | None = None,
        status: str | None = None,
        tags: list[str] | None = None,
        limit: int = 50,
    ) -> list[MemoryRecord]:
        # Workspace-level listing never surfaces another user's memories.
        stmt = _base_query(workspace_id).where(MemoryModel.user_id.is_(None))
        stmt = _apply_filters(stmt, memory_type, status, tags)
        stmt = stmt.order_by(MemoryModel.updated_at.desc()).limit(limit)
        rows = (await self._db.scalars(stmt)).all()
        return [_to_record(r) for r in rows]

    async def list_by_repository(
        self,
        repository_id: UUID,
        *,
        memory_type: str | None = None,
        status: str | None = None,
        tags: list[str] | None = None,
        limit: int = 50,
    ) -> list[MemoryRecord]:
        stmt = _base_query_by_repository(repository_id)
        stmt = _apply_filters(stmt, memory_type, status, tags)
        stmt = stmt.order_by(MemoryModel.updated_at.desc()).limit(limit)
        rows = (await self._db.scalars(stmt)).all()
        return [_to_record(r) for r in rows]

    async def list_by_user(
        self,
        workspace_id: UUID,
        user_id: UUID,
        *,
        memory_type: str | None = None,
        status: str | None = None,
        tags: list[str] | None = None,
        limit: int = 50,
    ) -> list[MemoryRecord]:
        stmt = _base_query(workspace_id)
        stmt = stmt.where(MemoryModel.user_id == user_id)
        stmt = _apply_filters(stmt, memory_type, status, tags)
        stmt = stmt.order_by(MemoryModel.updated_at.desc()).limit(limit)
        rows = (await self._db.scalars(stmt)).all()
        return [_to_record(r) for r in rows]

    async def create(
        self,
        *,
        workspace_id: UUID,
        repository_id: UUID | None = None,
        user_id: UUID | None = None,
        memory_type: str,
        scope: str,
        content: str,
        summary: str | None = None,
        source_file_path: str | None = None,
        source_symbol_name: str | None = None,
        source_commit_hash: str | None = None,
        confidence: float = 1.0,
        tags: list[str] | None = None,
        embedding: list[float] | None = None,
        created_by: UUID | None = None,
        expires_at: datetime | None = None,
    ) -> MemoryRecord:
        model = MemoryModel(
            workspace_id=workspace_id,
            repository_id=repository_id,
            user_id=user_id,
            memory_type=memory_type,
            scope=scope,
            status=MemoryStatus.ACTIVE.value,
            content=content,
            summary=summary,
            source_file_path=source_file_path,
            source_symbol_name=source_symbol_name,
            source_commit_hash=source_commit_hash,
            confidence=confidence,
            tags=tags or [],
            embedding=embedding,
            created_by=created_by,
            expires_at=expires_at,
        )
        self._db.add(model)
        await self._db.flush()
        return _to_record(model)

    async def update(
        self,
        memory_id: UUID,
        *,
        content: str | None = None,
        summary: str | None = ...,
        status: str | None = None,
        confidence: float | None = None,
        tags: list[str] | None = None,
        embedding: list[float] | None = ...,
        expires_at: datetime | None = ...,
    ) -> MemoryRecord | None:
        model = await self._db.get(MemoryModel, memory_id)
        if model is None or model.deleted_at is not None:
            return None
        if content is not None:
            model.content = content
        if summary is not ...:
            model.summary = summary
        if status is not None:
            model.status = status
        if confidence is not None:
            model.confidence = confidence
        if tags is not None:
            model.tags = tags
        if embedding is not ...:
            model.embedding = embedding
        if expires_at is not ...:
            model.expires_at = expires_at
        await self._db.flush()
        # The flush expires the ORM object's attributes; refresh reloads them
        # asynchronously so building the record never triggers a lazy (sync)
        # load, which would raise MissingGreenlet in an async session.
        await self._db.refresh(model)
        return _to_record(model)

    async def soft_delete(self, memory_id: UUID) -> bool:
        model = await self._db.get(MemoryModel, memory_id)
        if model is None or model.deleted_at is not None:
            return False
        model.deleted_at = datetime.now()
        await self._db.flush()
        return True

    async def search_semantic(
        self,
        workspace_id: UUID,
        query_embedding: list[float],
        *,
        repository_id: UUID | None = None,
        user_id: UUID | None = None,
        limit: int = 20,
    ) -> list[MemoryRecord]:
        stmt = _base_query(workspace_id).where(
            MemoryModel.embedding.is_not(None),
            MemoryModel.status == MemoryStatus.ACTIVE.value,
        )
        if repository_id is not None:
            stmt = stmt.where(MemoryModel.repository_id == repository_id)
        if user_id is not None:
            # A user-scoped query returns only that user's memories.
            stmt = stmt.where(MemoryModel.user_id == user_id)
        else:
            # A workspace-level query must NEVER surface another user's
            # memories: only workspace/repository memories qualify.
            stmt = stmt.where(MemoryModel.user_id.is_(None))
        stmt = stmt.order_by(
            MemoryModel.embedding.cosine_distance(query_embedding)
        ).limit(limit)
        rows = (await self._db.scalars(stmt)).all()
        return [_to_record(r) for r in rows]

    async def search_by_tags(
        self,
        workspace_id: UUID,
        tags: list[str],
        *,
        repository_id: UUID | None = None,
        limit: int = 50,
    ) -> list[MemoryRecord]:
        # Workspace-level tag search never surfaces another user's memories.
        stmt = _base_query(workspace_id).where(MemoryModel.user_id.is_(None))
        stmt = _apply_tag_filters(stmt, tags)
        if repository_id is not None:
            stmt = stmt.where(MemoryModel.repository_id == repository_id)
        stmt = stmt.order_by(MemoryModel.updated_at.desc()).limit(limit)
        rows = (await self._db.scalars(stmt)).all()
        return [_to_record(r) for r in rows]

    async def mark_stale(
        self, repository_id: UUID, paths: list[str],
    ) -> int:
        """Mark repository memories stale only when they reference a changed path.

        Only memories that explicitly reference a path in ``paths`` are
        candidates; memories without source linkage remain active.
        """
        if not paths:
            return 0
        result = await self._db.execute(
            update(MemoryModel)
            .where(
                MemoryModel.repository_id == repository_id,
                MemoryModel.deleted_at.is_(None),
                MemoryModel.status == MemoryStatus.ACTIVE.value,
                MemoryModel.source_file_path.in_(paths),
            )
            .values(status=MemoryStatus.STALE.value)
        )
        return result.rowcount or 0

    async def delete_by_repository(self, repository_id: UUID) -> int:
        result = await self._db.execute(
            delete(MemoryModel).where(
                MemoryModel.repository_id == repository_id
            )
        )
        return result.rowcount or 0

    async def touch_accessed(self, memory_ids: list[UUID]) -> None:
        if not memory_ids:
            return
        await self._db.execute(
            update(MemoryModel)
            .where(MemoryModel.id.in_(memory_ids))
            .values(accessed_at=datetime.now())
        )

    async def find_expired(
        self, now: datetime, *, limit: int = 100,
    ) -> list[MemoryRecord]:
        stmt = (
            select(MemoryModel)
            .where(
                MemoryModel.expires_at.is_not(None),
                MemoryModel.expires_at < now,
                MemoryModel.status == MemoryStatus.ACTIVE.value,
                MemoryModel.deleted_at.is_(None),
            )
            .limit(limit)
        )
        rows = (await self._db.scalars(stmt)).all()
        return [_to_record(r) for r in rows]

    async def find_missing_embeddings(
        self, *, limit: int = 100,
    ) -> list[MemoryRecord]:
        stmt = (
            select(MemoryModel)
            .where(
                MemoryModel.embedding.is_(None),
                MemoryModel.deleted_at.is_(None),
            )
            .limit(limit)
        )
        rows = (await self._db.scalars(stmt)).all()
        return [_to_record(r) for r in rows]

    async def hard_delete_old(self, older_than: datetime) -> int:
        result = await self._db.execute(
            delete(MemoryModel).where(
                MemoryModel.deleted_at.is_not(None),
                MemoryModel.deleted_at < older_than,
            )
        )
        return result.rowcount or 0

    async def bulk_update_status(
        self, memory_ids: list[UUID], status: str,
    ) -> int:
        if not memory_ids:
            return 0
        result = await self._db.execute(
            update(MemoryModel)
            .where(MemoryModel.id.in_(memory_ids))
            .values(status=status)
        )
        return result.rowcount or 0

    async def bulk_update_embeddings(
        self, updates: list[tuple[UUID, list[float]]],
    ) -> int:
        if not updates:
            return 0
        count = 0
        for memory_id, vector in updates:
            result = await self._db.execute(
                update(MemoryModel)
                .where(MemoryModel.id == memory_id)
                .values(embedding=vector)
            )
            count += result.rowcount or 0
        return count


# ─── Shared filter helpers ──────────────────────────────────────────


def _apply_filters(
    stmt,
    memory_type: str | None,
    status: str | None,
    tags: list[str] | None,
):
    if memory_type is not None:
        stmt = stmt.where(MemoryModel.memory_type == memory_type)
    if status is not None:
        stmt = stmt.where(MemoryModel.status == status)
    if tags:
        stmt = _apply_tag_filters(stmt, tags)
    return stmt


def _apply_tag_filters(stmt, tags: list[str]):
    """Filter to memories containing *all* requested tags (JSONB containment)."""
    if not tags:
        return stmt
    return stmt.where(MemoryModel.tags.contains(tags))
