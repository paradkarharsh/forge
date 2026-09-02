"""SQLAlchemy adapter for message persistence."""
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from forge_api.domain.conversation import MessageRecord, MessageStatus
from forge_api.infrastructure.database.models import MessageModel


def _to_record(row: MessageModel) -> MessageRecord:
    return MessageRecord(
        id=row.id,
        conversation_id=row.conversation_id,
        role=row.role,
        content=row.content,
        provider=row.provider,
        model=row.model,
        prompt_version=row.prompt_version,
        input_tokens=row.input_tokens,
        output_tokens=row.output_tokens,
        total_tokens=row.total_tokens,
        duration_ms=row.duration_ms,
        finish_reason=row.finish_reason,
        status=MessageStatus(row.status),
        metadata=row.metadata_ or {},
        created_at=row.created_at,
    )


class SqlMessageRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get(self, message_id: UUID) -> MessageRecord | None:
        result = await self._db.execute(
            select(MessageModel).where(MessageModel.id == message_id)
        )
        row = result.scalar_one_or_none()
        return _to_record(row) if row else None

    async def list_by_conversation(
        self,
        conversation_id: UUID,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[MessageRecord]:
        result = await self._db.execute(
            select(MessageModel)
            .where(MessageModel.conversation_id == conversation_id)
            .order_by(MessageModel.created_at.asc())
            .limit(limit)
            .offset(offset)
        )
        return [_to_record(r) for r in result.scalars().all()]

    async def count_by_conversation(
        self, conversation_id: UUID,
    ) -> int:
        result = await self._db.execute(
            select(func.count())
            .select_from(MessageModel)
            .where(MessageModel.conversation_id == conversation_id)
        )
        return result.scalar_one()

    async def create(
        self,
        *,
        conversation_id: UUID,
        role: str,
        content: str,
        provider: str | None = None,
        model: str | None = None,
        prompt_version: str | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        total_tokens: int | None = None,
        duration_ms: float | None = None,
        finish_reason: str | None = None,
        status: str = "complete",
        metadata: dict | None = None,
    ) -> MessageRecord:
        row = MessageModel(
            conversation_id=conversation_id,
            role=role,
            content=content,
            provider=provider,
            model=model,
            prompt_version=prompt_version,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            duration_ms=duration_ms,
            finish_reason=finish_reason,
            status=status,
            metadata_=metadata or {},
        )
        self._db.add(row)
        await self._db.flush()
        await self._db.refresh(row)
        return _to_record(row)

    async def update(
        self,
        message_id: UUID,
        *,
        content: str | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        total_tokens: int | None = None,
        duration_ms: float | None = None,
        finish_reason: str | None = None,
        status: str | None = None,
        metadata: dict | None = None,
    ) -> MessageRecord | None:
        values: dict = {}
        if content is not None:
            values["content"] = content
        if input_tokens is not None:
            values["input_tokens"] = input_tokens
        if output_tokens is not None:
            values["output_tokens"] = output_tokens
        if total_tokens is not None:
            values["total_tokens"] = total_tokens
        if duration_ms is not None:
            values["duration_ms"] = duration_ms
        if finish_reason is not None:
            values["finish_reason"] = finish_reason
        if status is not None:
            values["status"] = status
        if metadata is not None:
            values["metadata_"] = metadata
        if not values:
            return await self.get(message_id)

        result = await self._db.execute(
            update(MessageModel)
            .where(MessageModel.id == message_id)
            .values(**values)
            .returning(MessageModel)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        await self._db.flush()
        return _to_record(row)
