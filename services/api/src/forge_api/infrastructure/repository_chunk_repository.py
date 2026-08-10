"""SQLAlchemy adapter for the RepositoryChunkRepository protocol.

Semantic search uses pgvector's cosine distance operator (``<=>``)
exposed by the ``Vector`` type's ``cosine_distance`` helper.
"""
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from forge_api.domain.indexing import ChunkRecord
from forge_api.infrastructure.database.models import RepositoryChunkModel


def _to_record(model: RepositoryChunkModel) -> ChunkRecord:
    return ChunkRecord(
        id=model.id,
        file_id=model.file_id,
        repository_id=model.repository_id,
        chunk_index=model.chunk_index,
        content=model.content,
        line_start=model.line_start,
        line_end=model.line_end,
        token_count=model.token_count,
        embedding=list(model.embedding) if model.embedding is not None else None,
    )


class SqlRepositoryChunkRepository:
    """Concrete SQLAlchemy implementation of ``RepositoryChunkRepository``."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def list_by_file(self, file_id: UUID) -> list[ChunkRecord]:
        rows = (
            await self._db.scalars(
                select(RepositoryChunkModel)
                .where(RepositoryChunkModel.file_id == file_id)
                .order_by(RepositoryChunkModel.chunk_index)
            )
        ).all()
        return [_to_record(r) for r in rows]

    async def search_semantic(
        self,
        repository_id: UUID,
        query_embedding: list[float],
        *,
        limit: int = 20,
    ) -> list[ChunkRecord]:
        rows = (
            await self._db.scalars(
                select(RepositoryChunkModel)
                .where(
                    RepositoryChunkModel.repository_id == repository_id,
                    RepositoryChunkModel.embedding.is_not(None),
                )
                .order_by(
                    RepositoryChunkModel.embedding.cosine_distance(query_embedding)
                )
                .limit(limit)
            )
        ).all()
        return [_to_record(r) for r in rows]

    async def bulk_create(self, chunks: list[ChunkRecord]) -> None:
        if not chunks:
            return
        for chunk in chunks:
            self._db.add(
                RepositoryChunkModel(
                    id=chunk.id,
                    file_id=chunk.file_id,
                    repository_id=chunk.repository_id,
                    chunk_index=chunk.chunk_index,
                    content=chunk.content,
                    line_start=chunk.line_start,
                    line_end=chunk.line_end,
                    token_count=chunk.token_count,
                    embedding=chunk.embedding,
                )
            )
        await self._db.flush()

    async def delete_by_file(self, file_id: UUID) -> int:
        result = await self._db.execute(
            delete(RepositoryChunkModel).where(
                RepositoryChunkModel.file_id == file_id
            )
        )
        return result.rowcount or 0

    async def delete_by_repository(self, repository_id: UUID) -> int:
        result = await self._db.execute(
            delete(RepositoryChunkModel).where(
                RepositoryChunkModel.repository_id == repository_id
            )
        )
        return result.rowcount or 0