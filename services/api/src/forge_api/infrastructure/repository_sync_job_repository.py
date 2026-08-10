"""SQLAlchemy adapter for the RepositorySyncJobRepository protocol."""
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from forge_api.domain.repository import SyncJobRecord, SyncJobStatus
from forge_api.infrastructure.database.models import RepositorySyncJobModel


def _to_record(model: RepositorySyncJobModel) -> SyncJobRecord:
    return SyncJobRecord(
        id=model.id,
        repository_id=model.repository_id,
        job_type=model.job_type,
        status=SyncJobStatus(model.status),
        started_at=model.started_at,
        completed_at=model.completed_at,
        error_message=model.error_message,
        created_at=model.created_at,
    )


class SqlRepositorySyncJobRepository:
    """Concrete SQLAlchemy implementation of ``RepositorySyncJobRepository``."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get(self, job_id: UUID) -> SyncJobRecord | None:
        model = await self._db.get(RepositorySyncJobModel, job_id)
        return _to_record(model) if model else None

    async def list_by_repository(
        self, repository_id: UUID, *, job_type: str | None = None
    ) -> list[SyncJobRecord]:
        stmt = select(RepositorySyncJobModel).where(
            RepositorySyncJobModel.repository_id == repository_id
        )
        if job_type is not None:
            stmt = stmt.where(RepositorySyncJobModel.job_type == job_type)
        stmt = stmt.order_by(RepositorySyncJobModel.created_at.desc())
        rows = (await self._db.scalars(stmt)).all()
        return [_to_record(r) for r in rows]

    async def create(
        self,
        *,
        repository_id: UUID,
        job_type: str,
        status: str = "pending",
    ) -> SyncJobRecord:
        model = RepositorySyncJobModel(
            repository_id=repository_id,
            job_type=job_type,
            status=status,
        )
        self._db.add(model)
        await self._db.flush()
        return _to_record(model)

    async def update_status(
        self,
        job_id: UUID,
        *,
        status: str,
        error_message: str | None = None,
    ) -> SyncJobRecord | None:
        model = await self._db.get(RepositorySyncJobModel, job_id)
        if not model:
            return None
        model.status = status
        if status == SyncJobStatus.RUNNING and model.started_at is None:
            model.started_at = datetime.now(UTC)
        if status in (SyncJobStatus.COMPLETED, SyncJobStatus.FAILED):
            model.completed_at = datetime.now(UTC)
        if error_message is not None:
            model.error_message = error_message
        await self._db.flush()
        return _to_record(model)
