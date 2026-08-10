"""SQLAlchemy adapter for the RepositoryDependencyRepository protocol."""
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from forge_api.domain.indexing import DependencyKind, DependencyRecord
from forge_api.infrastructure.database.models import RepositoryDependencyModel


def _to_record(model: RepositoryDependencyModel) -> DependencyRecord:
    return DependencyRecord(
        id=model.id,
        repository_id=model.repository_id,
        source_file_id=model.source_file_id,
        target_path=model.target_path,
        target_file_id=model.target_file_id,
        kind=DependencyKind(model.kind),
        is_external=model.is_external,
    )


class SqlRepositoryDependencyRepository:
    """Concrete SQLAlchemy implementation of ``RepositoryDependencyRepository``."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def list_by_file(self, source_file_id: UUID) -> list[DependencyRecord]:
        rows = (
            await self._db.scalars(
                select(RepositoryDependencyModel).where(
                    RepositoryDependencyModel.source_file_id == source_file_id
                )
            )
        ).all()
        return [_to_record(r) for r in rows]

    async def list_dependents(self, target_file_id: UUID) -> list[DependencyRecord]:
        rows = (
            await self._db.scalars(
                select(RepositoryDependencyModel).where(
                    RepositoryDependencyModel.target_file_id == target_file_id
                )
            )
        ).all()
        return [_to_record(r) for r in rows]

    async def bulk_create(self, dependencies: list[DependencyRecord]) -> None:
        if not dependencies:
            return
        for dep in dependencies:
            self._db.add(
                RepositoryDependencyModel(
                    id=dep.id,
                    repository_id=dep.repository_id,
                    source_file_id=dep.source_file_id,
                    target_path=dep.target_path,
                    target_file_id=dep.target_file_id,
                    kind=dep.kind.value,
                    is_external=dep.is_external,
                )
            )
        await self._db.flush()

    async def delete_by_file(self, source_file_id: UUID) -> int:
        result = await self._db.execute(
            delete(RepositoryDependencyModel).where(
                RepositoryDependencyModel.source_file_id == source_file_id
            )
        )
        return result.rowcount or 0

    async def delete_by_repository(self, repository_id: UUID) -> int:
        result = await self._db.execute(
            delete(RepositoryDependencyModel).where(
                RepositoryDependencyModel.repository_id == repository_id
            )
        )
        return result.rowcount or 0