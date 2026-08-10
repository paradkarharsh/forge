"""SQLAlchemy adapter for the RepositoryBranchRepository protocol."""
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from forge_api.domain.repository import BranchRecord
from forge_api.infrastructure.database.models import RepositoryBranchModel


def _to_record(model: RepositoryBranchModel) -> BranchRecord:
    return BranchRecord(
        id=model.id,
        repository_id=model.repository_id,
        name=model.name,
        commit_hash=model.commit_hash,
        is_default=model.is_default,
        is_protected=model.is_protected,
        created_at=model.created_at,
    )


class SqlRepositoryBranchRepository:
    """Concrete SQLAlchemy implementation of ``RepositoryBranchRepository``."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def list_by_repository(self, repository_id: UUID) -> list[BranchRecord]:
        rows = (
            await self._db.scalars(
                select(RepositoryBranchModel)
                .where(RepositoryBranchModel.repository_id == repository_id)
                .order_by(RepositoryBranchModel.name)
            )
        ).all()
        return [_to_record(r) for r in rows]

    async def upsert(
        self,
        *,
        repository_id: UUID,
        name: str,
        commit_hash: str | None = None,
        is_default: bool = False,
        is_protected: bool = False,
    ) -> BranchRecord:
        existing = await self._db.scalar(
            select(RepositoryBranchModel).where(
                RepositoryBranchModel.repository_id == repository_id,
                RepositoryBranchModel.name == name,
            )
        )
        if existing:
            existing.commit_hash = commit_hash
            existing.is_default = is_default
            existing.is_protected = is_protected
            await self._db.flush()
            return _to_record(existing)

        model = RepositoryBranchModel(
            repository_id=repository_id,
            name=name,
            commit_hash=commit_hash,
            is_default=is_default,
            is_protected=is_protected,
        )
        self._db.add(model)
        await self._db.flush()
        return _to_record(model)

    async def delete_by_repository(self, repository_id: UUID) -> int:
        result = await self._db.execute(
            delete(RepositoryBranchModel).where(
                RepositoryBranchModel.repository_id == repository_id
            )
        )
        return result.rowcount
