"""SQLAlchemy adapter for the RepositoryEventRepository protocol."""
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from forge_api.domain.repository import RepositoryEventRecord
from forge_api.infrastructure.database.models import RepositoryEventModel


def _to_record(model: RepositoryEventModel) -> RepositoryEventRecord:
    return RepositoryEventRecord(
        id=model.id,
        repository_id=model.repository_id,
        event_type=model.event_type,
        actor_id=model.actor_id,
        payload=model.payload,
        created_at=model.created_at,
    )


class SqlRepositoryEventRepository:
    """Concrete SQLAlchemy implementation of ``RepositoryEventRepository``."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def list_by_repository(
        self, repository_id: UUID, *, limit: int = 50
    ) -> list[RepositoryEventRecord]:
        rows = (
            await self._db.scalars(
                select(RepositoryEventModel)
                .where(RepositoryEventModel.repository_id == repository_id)
                .order_by(RepositoryEventModel.created_at.desc())
                .limit(limit)
            )
        ).all()
        return [_to_record(r) for r in rows]

    async def create(
        self,
        *,
        repository_id: UUID,
        event_type: str,
        actor_id: UUID | None = None,
        payload: dict[str, Any] | None = None,
    ) -> RepositoryEventRecord:
        model = RepositoryEventModel(
            repository_id=repository_id,
            event_type=event_type,
            actor_id=actor_id,
            payload=payload,
        )
        self._db.add(model)
        await self._db.flush()
        return _to_record(model)
