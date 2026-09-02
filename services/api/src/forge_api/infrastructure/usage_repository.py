"""SQLAlchemy adapter for usage event persistence."""
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from forge_api.domain.conversation import UsageEventRecord
from forge_api.infrastructure.database.models import UsageEventModel


def _to_record(row: UsageEventModel) -> UsageEventRecord:
    return UsageEventRecord(
        id=row.id,
        workspace_id=row.workspace_id,
        user_id=row.user_id,
        conversation_id=row.conversation_id,
        message_id=row.message_id,
        provider=row.provider,
        model=row.model,
        input_tokens=row.input_tokens,
        output_tokens=row.output_tokens,
        total_tokens=row.total_tokens,
        duration_ms=row.duration_ms,
        estimated_cost=row.estimated_cost,
        created_at=row.created_at,
        metadata=row.metadata_ or {},
    )


class SqlUsageEventRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(
        self,
        *,
        workspace_id: UUID,
        user_id: UUID,
        conversation_id: UUID | None = None,
        message_id: UUID | None = None,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        total_tokens: int,
        duration_ms: float,
        estimated_cost: float,
        metadata: dict | None = None,
    ) -> UsageEventRecord:
        row = UsageEventModel(
            workspace_id=workspace_id,
            user_id=user_id,
            conversation_id=conversation_id,
            message_id=message_id,
            provider=provider,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            duration_ms=duration_ms,
            estimated_cost=estimated_cost,
            metadata_=metadata or {},
        )
        self._db.add(row)
        await self._db.flush()
        await self._db.refresh(row)
        return _to_record(row)

    async def list_by_workspace(
        self,
        workspace_id: UUID,
        *,
        user_id: UUID | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[UsageEventRecord]:
        q = (
            select(UsageEventModel)
            .where(UsageEventModel.workspace_id == workspace_id)
            .order_by(UsageEventModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        if user_id is not None:
            q = q.where(UsageEventModel.user_id == user_id)
        if start is not None:
            q = q.where(UsageEventModel.created_at >= start)
        if end is not None:
            q = q.where(UsageEventModel.created_at <= end)
        result = await self._db.execute(q)
        return [_to_record(r) for r in result.scalars().all()]

    async def aggregate_by_workspace(
        self,
        workspace_id: UUID,
        *,
        user_id: UUID | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> dict:
        q = select(
            func.count().label("total_requests"),
            func.coalesce(func.sum(UsageEventModel.input_tokens), 0).label(
                "total_input_tokens"
            ),
            func.coalesce(func.sum(UsageEventModel.output_tokens), 0).label(
                "total_output_tokens"
            ),
            func.coalesce(func.sum(UsageEventModel.total_tokens), 0).label(
                "total_tokens"
            ),
            func.coalesce(func.sum(UsageEventModel.estimated_cost), 0.0).label(
                "total_cost"
            ),
        ).where(UsageEventModel.workspace_id == workspace_id)

        if user_id is not None:
            q = q.where(UsageEventModel.user_id == user_id)
        if start is not None:
            q = q.where(UsageEventModel.created_at >= start)
        if end is not None:
            q = q.where(UsageEventModel.created_at <= end)

        result = await self._db.execute(q)
        row = result.one()
        return {
            "total_requests": row.total_requests,
            "total_input_tokens": row.total_input_tokens,
            "total_output_tokens": row.total_output_tokens,
            "total_tokens": row.total_tokens,
            "total_cost": float(row.total_cost),
        }
