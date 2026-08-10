"""SQLAlchemy adapter for the RepositorySymbolRepository protocol."""
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from forge_api.domain.indexing import SymbolKind, SymbolRecord
from forge_api.infrastructure.database.models import RepositorySymbolModel


def _to_record(model: RepositorySymbolModel) -> SymbolRecord:
    return SymbolRecord(
        id=model.id,
        file_id=model.file_id,
        repository_id=model.repository_id,
        name=model.name,
        kind=SymbolKind(model.kind),
        signature=model.signature,
        line_start=model.line_start,
        line_end=model.line_end,
        parent_symbol_id=model.parent_symbol_id,
    )


class SqlRepositorySymbolRepository:
    """Concrete SQLAlchemy implementation of ``RepositorySymbolRepository``."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def list_by_file(self, file_id: UUID) -> list[SymbolRecord]:
        rows = (
            await self._db.scalars(
                select(RepositorySymbolModel)
                .where(RepositorySymbolModel.file_id == file_id)
                .order_by(RepositorySymbolModel.line_start)
            )
        ).all()
        return [_to_record(r) for r in rows]

    async def list_by_repository(
        self, repository_id: UUID, *, kind: str | None = None
    ) -> list[SymbolRecord]:
        stmt = select(RepositorySymbolModel).where(
            RepositorySymbolModel.repository_id == repository_id
        )
        if kind is not None:
            stmt = stmt.where(RepositorySymbolModel.kind == kind)
        stmt = stmt.order_by(RepositorySymbolModel.line_start)
        rows = (await self._db.scalars(stmt)).all()
        return [_to_record(r) for r in rows]

    async def search_by_name(
        self,
        repository_id: UUID,
        query: str,
        *,
        kind: str | None = None,
        limit: int = 50,
    ) -> list[SymbolRecord]:
        pattern = f"%{query}%"
        stmt = (
            select(RepositorySymbolModel)
            .where(
                RepositorySymbolModel.repository_id == repository_id,
                RepositorySymbolModel.name.ilike(pattern),
            )
            .order_by(RepositorySymbolModel.name)
            .limit(limit)
        )
        if kind is not None:
            stmt = stmt.where(RepositorySymbolModel.kind == kind)
        rows = (await self._db.scalars(stmt)).all()
        return [_to_record(r) for r in rows]

    async def bulk_create(self, symbols: list[SymbolRecord]) -> None:
        if not symbols:
            return
        for symbol in symbols:
            self._db.add(
                RepositorySymbolModel(
                    id=symbol.id,
                    file_id=symbol.file_id,
                    repository_id=symbol.repository_id,
                    name=symbol.name,
                    kind=symbol.kind.value,
                    signature=symbol.signature,
                    line_start=symbol.line_start,
                    line_end=symbol.line_end,
                    parent_symbol_id=symbol.parent_symbol_id,
                )
            )
        await self._db.flush()

    async def delete_by_file(self, file_id: UUID) -> int:
        result = await self._db.execute(
            delete(RepositorySymbolModel).where(
                RepositorySymbolModel.file_id == file_id
            )
        )
        return result.rowcount or 0

    async def delete_by_repository(self, repository_id: UUID) -> int:
        result = await self._db.execute(
            delete(RepositorySymbolModel).where(
                RepositorySymbolModel.repository_id == repository_id
            )
        )
        return result.rowcount or 0