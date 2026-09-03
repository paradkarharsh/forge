"""SQLAlchemy adapter for the AgentToolCallRepository protocol."""
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from forge_api.domain.agent import AgentToolCallRecord, ToolCallStatus
from forge_api.domain.tool import RiskLevel
from forge_api.infrastructure.database.models import AgentToolCallModel


def _to_record(model: AgentToolCallModel) -> AgentToolCallRecord:
    return AgentToolCallRecord(
        id=model.id,
        session_id=model.session_id,
        tool_name=model.tool_name,
        arguments=dict(model.arguments or {}),
        risk_level=RiskLevel(model.risk_level),
        status=ToolCallStatus(model.status),
        created_at=model.created_at,
        step_id=model.step_id,
        approval_id=model.approval_id,
        output=model.output,
        error_message=model.error_message,
        duration_ms=model.duration_ms,
        started_at=model.started_at,
        completed_at=model.completed_at,
        metadata=dict(model.metadata_ or {}),
    )


class SqlAgentToolCallRepository:
    """Concrete SQLAlchemy implementation of AgentToolCallRepository."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get(self, tool_call_id: UUID) -> AgentToolCallRecord | None:
        model = await self._db.get(AgentToolCallModel, tool_call_id)
        return _to_record(model) if model else None

    async def list_by_session(
        self,
        session_id: UUID,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AgentToolCallRecord]:
        stmt = (
            select(AgentToolCallModel)
            .where(AgentToolCallModel.session_id == session_id)
            .order_by(AgentToolCallModel.created_at.asc())
            .limit(limit)
            .offset(offset)
        )
        rows = (await self._db.scalars(stmt)).all()
        return [_to_record(r) for r in rows]

    async def create(
        self,
        *,
        session_id: UUID,
        tool_name: str,
        arguments: dict[str, Any],
        risk_level: RiskLevel,
        status: ToolCallStatus = ToolCallStatus.PENDING_APPROVAL,
        step_id: UUID | None = None,
        approval_id: UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AgentToolCallRecord:
        model = AgentToolCallModel(
            session_id=session_id,
            tool_name=tool_name,
            arguments=arguments,
            risk_level=risk_level.value,
            status=status.value,
            step_id=step_id,
            approval_id=approval_id,
            metadata_=metadata or {},
        )
        self._db.add(model)
        await self._db.flush()
        return _to_record(model)

    async def complete(
        self,
        tool_call_id: UUID,
        *,
        status: ToolCallStatus,
        output: str | None = None,
        error_message: str | None = None,
        duration_ms: float | None = None,
        completed_at: datetime | None = None,
    ) -> AgentToolCallRecord | None:
        model = await self._db.get(AgentToolCallModel, tool_call_id)
        if not model:
            return None

        model.status = status.value
        if output is not None:
            model.output = output
        if error_message is not None:
            model.error_message = error_message
        if duration_ms is not None:
            model.duration_ms = duration_ms

        if status == ToolCallStatus.RUNNING and model.started_at is None:
            model.started_at = datetime.now(UTC)

        if completed_at is not None:
            model.completed_at = completed_at
        elif (
            status in (ToolCallStatus.COMPLETED, ToolCallStatus.FAILED)
            and model.completed_at is None
        ):
            model.completed_at = datetime.now(UTC)



        await self._db.flush()
        return _to_record(model)
