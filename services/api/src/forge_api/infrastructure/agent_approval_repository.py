"""SQLAlchemy adapter for the AgentApprovalRepository protocol."""
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from forge_api.domain.approval import AgentApprovalRecord, ApprovalStatus
from forge_api.domain.errors import DomainError
from forge_api.infrastructure.database.models import AgentApprovalModel


def _to_record(model: AgentApprovalModel) -> AgentApprovalRecord:
    return AgentApprovalRecord(
        id=model.id,
        session_id=model.session_id,
        tool_call_id=model.tool_call_id,
        tool_name=model.tool_name,
        arguments_hash=model.arguments_hash,
        status=ApprovalStatus(model.status),
        requested_at=model.requested_at,
        requested_by=model.requested_by,
        decided_by=model.decided_by,
        reason=model.reason,
        decided_at=model.decided_at,
        expires_at=model.expires_at,
        metadata=dict(model.metadata_ or {}),
    )


class SqlAgentApprovalRepository:
    """Concrete SQLAlchemy implementation of AgentApprovalRepository."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get(self, approval_id: UUID) -> AgentApprovalRecord | None:
        model = await self._db.get(AgentApprovalModel, approval_id)
        return _to_record(model) if model else None

    async def get_by_tool_call(self, tool_call_id: UUID) -> AgentApprovalRecord | None:
        stmt = select(AgentApprovalModel).where(AgentApprovalModel.tool_call_id == tool_call_id)
        model = (await self._db.scalars(stmt)).first()
        return _to_record(model) if model else None

    async def list_pending_by_session(self, session_id: UUID) -> list[AgentApprovalRecord]:
        stmt = (
            select(AgentApprovalModel)
            .where(
                AgentApprovalModel.session_id == session_id,
                AgentApprovalModel.status == ApprovalStatus.PENDING.value,
            )
            .order_by(AgentApprovalModel.requested_at.asc())
        )
        rows = (await self._db.scalars(stmt)).all()
        return [_to_record(r) for r in rows]

    async def list_by_session(self, session_id: UUID) -> list[AgentApprovalRecord]:
        stmt = (
            select(AgentApprovalModel)
            .where(AgentApprovalModel.session_id == session_id)
            .order_by(AgentApprovalModel.requested_at.desc())
        )
        rows = (await self._db.scalars(stmt)).all()
        return [_to_record(r) for r in rows]

    async def create(
        self,
        *,
        session_id: UUID,
        tool_call_id: UUID,
        tool_name: str,
        arguments_hash: str,
        requested_by: UUID | None = None,
        expires_at: datetime | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AgentApprovalRecord:
        model = AgentApprovalModel(
            session_id=session_id,
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            arguments_hash=arguments_hash,
            status=ApprovalStatus.PENDING.value,
            requested_by=requested_by,
            expires_at=expires_at,
            metadata_=metadata or {},
        )
        self._db.add(model)
        await self._db.flush()
        return _to_record(model)

    async def decide(
        self,
        approval_id: UUID,
        *,
        status: ApprovalStatus,
        decided_by: UUID,
        reason: str | None = None,
        decided_at: datetime | None = None,
    ) -> AgentApprovalRecord | None:
        # Atomic lock row for update
        stmt = (
            select(AgentApprovalModel)
            .where(AgentApprovalModel.id == approval_id)
            .with_for_update()
        )
        model = (await self._db.scalars(stmt)).first()
        if not model:
            return None

        current_status = ApprovalStatus(model.status)
        if current_status != ApprovalStatus.PENDING:
            if current_status == status:
                # Idempotent repeated decision
                return _to_record(model)
            raise DomainError(
                f"Approval has already been decided with status '{current_status.value}'.",
                code="approval_already_decided",
            )

        model.status = status.value
        model.decided_by = decided_by
        model.reason = reason
        model.decided_at = decided_at or datetime.now(UTC)

        await self._db.flush()
        return _to_record(model)
