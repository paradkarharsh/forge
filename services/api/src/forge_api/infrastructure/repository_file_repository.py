"""SQLAlchemy adapter for the RepositoryFileRepository protocol."""
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from forge_api.domain.indexing import FileRecord
from forge_api.infrastructure.database.models import RepositoryFileModel


def _to_record(model: RepositoryFileModel) -> FileRecord:
    return FileRecord(
        id=model.id,
        repository_id=model.repository_id,
        path=model.path,
        language=model.language,
        size_bytes=model.size_bytes,
        line_count=model.line_count,
        commit_hash=model.commit_hash,
        content_hash=model.content_hash,
        indexed_at=model.indexed_at,
    )


class SqlRepositoryFileRepository:
    """Concrete SQLAlchemy implementation of ``RepositoryFileRepository``."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get(self, file_id: UUID) -> FileRecord | None:
        model = await self._db.get(RepositoryFileModel, file_id)
        return _to_record(model) if model else None

    async def get_by_path(
        self, repository_id: UUID, path: str
    ) -> FileRecord | None:
        model = (
            await self._db.scalars(
                select(RepositoryFileModel).where(
                    RepositoryFileModel.repository_id == repository_id,
                    RepositoryFileModel.path == path,
                )
            )
        ).first()
        return _to_record(model) if model else None

    async def list_by_repository(
        self, repository_id: UUID, *, language: str | None = None
    ) -> list[FileRecord]:
        stmt = select(RepositoryFileModel).where(
            RepositoryFileModel.repository_id == repository_id
        )
        if language is not None:
            stmt = stmt.where(RepositoryFileModel.language == language)
        stmt = stmt.order_by(RepositoryFileModel.path)
        rows = (await self._db.scalars(stmt)).all()
        return [_to_record(r) for r in rows]

    async def upsert(
        self,
        *,
        repository_id: UUID,
        path: str,
        language: str | None,
        size_bytes: int,
        line_count: int | None,
        commit_hash: str,
        content_hash: str,
    ) -> FileRecord:
        model = (
            await self._db.scalars(
                select(RepositoryFileModel).where(
                    RepositoryFileModel.repository_id == repository_id,
                    RepositoryFileModel.path == path,
                )
            )
        ).first()
        if model is not None:
            model.language = language
            model.size_bytes = size_bytes
            model.line_count = line_count
            model.commit_hash = commit_hash
            model.content_hash = content_hash
        else:
            model = RepositoryFileModel(
                repository_id=repository_id,
                path=path,
                language=language,
                size_bytes=size_bytes,
                line_count=line_count,
                commit_hash=commit_hash,
                content_hash=content_hash,
            )
            self._db.add(model)
        await self._db.flush()
        return _to_record(model)

    async def delete_by_repository(self, repository_id: UUID) -> int:
        result = await self._db.execute(
            delete(RepositoryFileModel).where(
                RepositoryFileModel.repository_id == repository_id
            )
        )
        return result.rowcount or 0

    async def delete_by_paths(
        self, repository_id: UUID, paths: list[str]
    ) -> int:
        if not paths:
            return 0
        result = await self._db.execute(
            delete(RepositoryFileModel).where(
                RepositoryFileModel.repository_id == repository_id,
                RepositoryFileModel.path.in_(paths),
            )
        )
        return result.rowcount or 0