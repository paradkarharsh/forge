"""SQLAlchemy adapter for conversation persistence."""
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from forge_api.domain.conversation import ConversationRecord, ConversationStatus
from forge_api.infrastructure.database.models import ConversationModel


def _to_record(row: ConversationModel) -> ConversationRecord:
    return ConversationRecord(
        id=row.id,
        workspace_id=row.workspace_id,
        user_id=row.user_id,
        title=row.title,
        repository_id=row.repository_id,
        status=ConversationStatus(row.status),
        message_count=row.message_count,
        created_at=row.created_at,
        updated_at=row.updated_at,
        deleted_at=row.deleted_at,
    )


class SqlConversationRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get(self, conversation_id: UUID) -> ConversationRecord | None:
        result = await self._db.execute(
            select(ConversationModel).where(ConversationModel.id == conversation_id)
        )
        row = result.scalar_one_or_none()
        return _to_record(row) if row else None

    async def list_by_workspace(
        self,
        workspace_id: UUID,
        user_id: UUID,
        *,
        limit: int = 50,
        offset: int = 0,
        include_deleted: bool = False,
    ) -> list[ConversationRecord]:
        q = (
            select(ConversationModel)
            .where(
                ConversationModel.workspace_id == workspace_id,
                ConversationModel.user_id == user_id,
            )
            .order_by(ConversationModel.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        if not include_deleted:
            q = q.where(ConversationModel.deleted_at.is_(None))
        result = await self._db.execute(q)
        return [_to_record(r) for r in result.scalars().all()]

    async def count_by_workspace(
        self,
        workspace_id: UUID,
        user_id: UUID,
        *,
        include_deleted: bool = False,
    ) -> int:
        q = select(func.count()).select_from(ConversationModel).where(
            ConversationModel.workspace_id == workspace_id,
            ConversationModel.user_id == user_id,
        )
        if not include_deleted:
            q = q.where(ConversationModel.deleted_at.is_(None))
        result = await self._db.execute(q)
        return result.scalar_one()

    async def create(
        self,
        *,
        workspace_id: UUID,
        user_id: UUID,
        title: str | None = None,
        repository_id: UUID | None = None,
    ) -> ConversationRecord:
        row = ConversationModel(
            workspace_id=workspace_id,
            user_id=user_id,
            title=title,
            repository_id=repository_id,
            status="active",
            message_count=0,
        )
        self._db.add(row)
        await self._db.flush()
        await self._db.refresh(row)
        return _to_record(row)

    async def update_title(
        self, conversation_id: UUID, title: str,
    ) -> ConversationRecord | None:
        result = await self._db.execute(
            update(ConversationModel)
            .where(ConversationModel.id == conversation_id)
            .values(title=title, updated_at=datetime.now(UTC))
            .returning(ConversationModel)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        await self._db.flush()
        return _to_record(row)

    async def increment_message_count(
        self, conversation_id: UUID,
    ) -> bool:
        result = await self._db.execute(
            update(ConversationModel)
            .where(ConversationModel.id == conversation_id)
            .values(
                message_count=ConversationModel.message_count + 1,
                updated_at=datetime.now(UTC),
            )
        )
        return result.rowcount > 0

    async def soft_delete(self, conversation_id: UUID) -> bool:
        result = await self._db.execute(
            update(ConversationModel)
            .where(
                ConversationModel.id == conversation_id,
                ConversationModel.deleted_at.is_(None),
            )
            .values(deleted_at=datetime.now(UTC))
        )
        return result.rowcount > 0
