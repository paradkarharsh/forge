"""SQLAlchemy adapter for the AgentStepRepository protocol."""
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from forge_api.domain.agent import AgentStepRecord, StepStatus
from forge_api.infrastructure.database.models import AgentStepModel


def _to_record(model: AgentStepModel) -> AgentStepRecord:
    return AgentStepRecord(
        id=model.id,
        session_id=model.session_id,
        sequence=model.sequence,
        objective=model.objective,
        status=StepStatus(model.status),
        created_at=model.created_at,
        started_at=model.started_at,
        completed_at=model.completed_at,
        metadata=dict(model.metadata_ or {}),
    )


class SqlAgentStepRepository:
    """Concrete SQLAlchemy implementation of AgentStepRepository."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get(self, step_id: UUID) -> AgentStepRecord | None:
        model = await self._db.get(AgentStepModel, step_id)
        return _to_record(model) if model else None

    async def list_by_session(self, session_id: UUID) -> list[AgentStepRecord]:
        stmt = (
            select(AgentStepModel)
            .where(AgentStepModel.session_id == session_id)
            .order_by(AgentStepModel.sequence.asc())
        )
        rows = (await self._db.scalars(stmt)).all()
        return [_to_record(r) for r in rows]

    async def create(
        self,
        *,
        session_id: UUID,
        sequence: int,
        objective: str,
        status: StepStatus = StepStatus.PENDING,
        metadata: dict[str, Any] | None = None,
    ) -> AgentStepRecord:
        model = AgentStepModel(
            session_id=session_id,
            sequence=sequence,
            objective=objective,
            status=status.value,
            metadata_=metadata or {},
        )
        self._db.add(model)
        await self._db.flush()
        return _to_record(model)

    async def update_status(
        self,
        step_id: UUID,
        status: StepStatus,
        *,
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
    ) -> AgentStepRecord | None:
        model = await self._db.get(AgentStepModel, step_id)
        if not model:
            return None

        model.status = status.value
        if started_at is not None:
            model.started_at = started_at
        elif status == StepStatus.RUNNING and model.started_at is None:
            model.started_at = datetime.now(UTC)

        if completed_at is not None:
            model.completed_at = completed_at
        elif status in (StepStatus.COMPLETED, StepStatus.FAILED) and model.completed_at is None:
            model.completed_at = datetime.now(UTC)

        await self._db.flush()
        return _to_record(model)
