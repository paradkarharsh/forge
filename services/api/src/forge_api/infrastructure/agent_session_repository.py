"""SQLAlchemy adapter for the AgentSessionRepository protocol."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from forge_api.domain.agent import (
    AgentLimits,
    AgentSessionRecord,
    AgentStatus,
    ExecutionMetrics,
)
from forge_api.infrastructure.database.models import AgentSessionModel


def _to_record(model: AgentSessionModel) -> AgentSessionRecord:
    limits = AgentLimits(**model.limits) if isinstance(model.limits, dict) else AgentLimits()
    metrics = (
        ExecutionMetrics(**model.metrics) if isinstance(model.metrics, dict) else ExecutionMetrics()
    )
    return AgentSessionRecord(
        id=model.id,
        workspace_id=model.workspace_id,
        user_id=model.user_id,
        objective=model.objective,
        status=AgentStatus(model.status),
        repository_id=model.repository_id,
        conversation_id=model.conversation_id,
        model=model.model,
        limits=limits,
        metrics=metrics,
        current_step=model.current_step,
        metadata=dict(model.metadata_ or {}),
        created_at=model.created_at,
        started_at=model.started_at,
        completed_at=model.completed_at,
        cancelled_at=model.cancelled_at,
        last_heartbeat_at=model.last_heartbeat_at,
        worker_id=model.worker_id,
        deleted_at=model.deleted_at,
    )


class SqlAgentSessionRepository:
    """Concrete SQLAlchemy implementation of AgentSessionRepository."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get(self, session_id: UUID) -> AgentSessionRecord | None:
        stmt = select(AgentSessionModel).where(
            AgentSessionModel.id == session_id,
            AgentSessionModel.deleted_at.is_(None),
        )
        model = (await self._db.scalars(stmt)).first()
        return _to_record(model) if model else None

    async def list_by_workspace(
        self,
        workspace_id: UUID,
        *,
        user_id: UUID | None = None,
        repository_id: UUID | None = None,
        status: AgentStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[AgentSessionRecord]:
        stmt = select(AgentSessionModel).where(
            AgentSessionModel.workspace_id == workspace_id,
            AgentSessionModel.deleted_at.is_(None),
        )
        if user_id is not None:
            stmt = stmt.where(AgentSessionModel.user_id == user_id)
        if repository_id is not None:
            stmt = stmt.where(AgentSessionModel.repository_id == repository_id)
        if status is not None:
            stmt = stmt.where(AgentSessionModel.status == status.value)

        stmt = stmt.order_by(AgentSessionModel.created_at.desc()).limit(limit).offset(offset)
        rows = (await self._db.scalars(stmt)).all()
        return [_to_record(r) for r in rows]

    async def count_by_workspace(
        self,
        workspace_id: UUID,
        *,
        user_id: UUID | None = None,
        repository_id: UUID | None = None,
        status: AgentStatus | None = None,
    ) -> int:
        stmt = (
            select(func.count())
            .select_from(AgentSessionModel)
            .where(
                AgentSessionModel.workspace_id == workspace_id,
                AgentSessionModel.deleted_at.is_(None),
            )
        )
        if user_id is not None:
            stmt = stmt.where(AgentSessionModel.user_id == user_id)
        if repository_id is not None:
            stmt = stmt.where(AgentSessionModel.repository_id == repository_id)
        if status is not None:
            stmt = stmt.where(AgentSessionModel.status == status.value)

        return (await self._db.scalar(stmt)) or 0

    async def create(
        self,
        *,
        workspace_id: UUID,
        user_id: UUID,
        objective: str,
        status: AgentStatus = AgentStatus.CREATED,
        repository_id: UUID | None = None,
        conversation_id: UUID | None = None,
        model: str | None = None,
        limits: AgentLimits | None = None,
        metrics: ExecutionMetrics | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AgentSessionRecord:
        lim = limits or AgentLimits()
        met = metrics or ExecutionMetrics()
        model_obj = AgentSessionModel(
            workspace_id=workspace_id,
            user_id=user_id,
            objective=objective,
            status=status.value,
            repository_id=repository_id,
            conversation_id=conversation_id,
            model=model,
            limits={
                "max_wall_time_seconds": lim.max_wall_time_seconds,
                "max_llm_calls": lim.max_llm_calls,
                "max_tool_calls": lim.max_tool_calls,
                "max_output_bytes": lim.max_output_bytes,
                "max_observation_bytes": lim.max_observation_bytes,
            },
            metrics={
                "total_llm_calls": met.total_llm_calls,
                "total_tool_calls": met.total_tool_calls,
                "prompt_tokens": met.prompt_tokens,
                "completion_tokens": met.completion_tokens,
                "total_tokens": met.total_tokens,
                "wall_time_seconds": met.wall_time_seconds,
                "estimated_cost": met.estimated_cost,
            },
            metadata_=metadata or {},
        )
        self._db.add(model_obj)
        await self._db.flush()
        return _to_record(model_obj)

    async def update_status(
        self,
        session_id: UUID,
        status: AgentStatus,
        *,
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
        cancelled_at: datetime | None = None,
    ) -> AgentSessionRecord | None:
        model = await self._db.get(AgentSessionModel, session_id)
        if not model or model.deleted_at is not None:
            return None

        model.status = status.value
        if started_at is not None:
            model.started_at = started_at
        elif status == AgentStatus.RUNNING and model.started_at is None:
            model.started_at = datetime.now(UTC)

        if completed_at is not None:
            model.completed_at = completed_at
        elif (
            status
            in (
                AgentStatus.COMPLETED,
                AgentStatus.FAILED,
                AgentStatus.TIMED_OUT,
                AgentStatus.EXPIRED,
            )
            and model.completed_at is None
        ):
            model.completed_at = datetime.now(UTC)

        if cancelled_at is not None:
            model.cancelled_at = cancelled_at
        elif status == AgentStatus.CANCELLED and model.cancelled_at is None:
            model.cancelled_at = datetime.now(UTC)

        await self._db.flush()
        return _to_record(model)

    async def update_metrics(
        self,
        session_id: UUID,
        metrics: ExecutionMetrics,
        *,
        current_step: int | None = None,
    ) -> AgentSessionRecord | None:
        model = await self._db.get(AgentSessionModel, session_id)
        if not model or model.deleted_at is not None:
            return None

        model.metrics = {
            "total_llm_calls": metrics.total_llm_calls,
            "total_tool_calls": metrics.total_tool_calls,
            "prompt_tokens": metrics.prompt_tokens,
            "completion_tokens": metrics.completion_tokens,
            "total_tokens": metrics.total_tokens,
            "wall_time_seconds": metrics.wall_time_seconds,
            "estimated_cost": metrics.estimated_cost,
        }
        if current_step is not None:
            model.current_step = current_step

        await self._db.flush()
        return _to_record(model)

    async def soft_delete(self, session_id: UUID) -> bool:
        model = await self._db.get(AgentSessionModel, session_id)
        if not model or model.deleted_at is not None:
            return False

        model.deleted_at = datetime.now(UTC)
        await self._db.flush()
        return True

    async def update_heartbeat(
        self,
        session_id: UUID,
        *,
        worker_id: str | None = None,
        heartbeat_at: datetime | None = None,
    ) -> bool:
        model = await self._db.get(AgentSessionModel, session_id)
        if not model or model.deleted_at is not None:
            return False

        model.last_heartbeat_at = heartbeat_at or datetime.now(UTC)
        if worker_id is not None:
            model.worker_id = worker_id
        await self._db.flush()
        return True

    async def list_stale_sessions(self, *, stale_before: datetime) -> list[AgentSessionRecord]:
        stmt = (
            select(AgentSessionModel)
            .where(
                AgentSessionModel.status.in_(
                    [
                        AgentStatus.RUNNING.value,
                        AgentStatus.PLANNING.value,
                    ]
                ),
                AgentSessionModel.deleted_at.is_(None),
                (
                    (
                        AgentSessionModel.last_heartbeat_at.is_not(None)
                        & (AgentSessionModel.last_heartbeat_at < stale_before)
                    )
                    | (
                        AgentSessionModel.last_heartbeat_at.is_(None)
                        & (AgentSessionModel.started_at < stale_before)
                    )
                    | (
                        AgentSessionModel.last_heartbeat_at.is_(None)
                        & AgentSessionModel.started_at.is_(None)
                        & (AgentSessionModel.created_at < stale_before)
                    )
                ),
            )
            .order_by(AgentSessionModel.created_at.asc())
        )
        rows = (await self._db.scalars(stmt)).all()
        return [_to_record(r) for r in rows]

    async def delete_terminal_sessions(self, *, completed_before: datetime) -> int:
        terminal_statuses = [
            AgentStatus.COMPLETED.value,
            AgentStatus.FAILED.value,
            AgentStatus.CANCELLED.value,
            AgentStatus.TIMED_OUT.value,
            AgentStatus.EXPIRED.value,
        ]
        stmt = select(AgentSessionModel.id).where(
            AgentSessionModel.status.in_(terminal_statuses),
            AgentSessionModel.completed_at.is_not(None),
            AgentSessionModel.completed_at < completed_before,
        )
        session_ids = (await self._db.scalars(stmt)).all()
        if not session_ids:
            return 0

        del_stmt = delete(AgentSessionModel).where(AgentSessionModel.id.in_(session_ids))
        res = await self._db.execute(del_stmt)
        await self._db.flush()
        return res.rowcount or len(session_ids)
