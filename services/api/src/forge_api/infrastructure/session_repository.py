"""SQLAlchemy adapter for the SessionRepository protocol."""
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from forge_api.domain.sessions import SessionRecord
from forge_api.infrastructure.database.models import SessionModel


def _to_record(model: SessionModel) -> SessionRecord:
    return SessionRecord(
        id=model.id,
        user_id=model.user_id,
        family_id=model.family_id,
        refresh_hash=model.refresh_hash,
        created_at=model.created_at,
        expires_at=model.expires_at,
        revoked_at=model.revoked_at,
        replaced_at=model.replaced_at,
        last_active_at=model.last_active_at,
        device_name=model.device_name,
        ip_address=model.ip_address,
        user_agent=model.user_agent,
    )


class SqlSessionRepository:
    """Concrete SQLAlchemy implementation of ``SessionRepository``."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get(
        self, session_id: UUID, *, user_id: UUID | None = None
    ) -> SessionRecord | None:
        stmt = select(SessionModel).where(SessionModel.id == session_id)
        if user_id is not None:
            stmt = stmt.where(SessionModel.user_id == user_id)
        model = await self._db.scalar(stmt)
        return _to_record(model) if model else None

    async def find_by_refresh_hash(self, refresh_hash: str) -> SessionRecord | None:
        model = await self._db.scalar(
            select(SessionModel).where(SessionModel.refresh_hash == refresh_hash)
        )
        return _to_record(model) if model else None

    async def list_active(self, user_id: UUID) -> list[SessionRecord]:
        now = datetime.now(UTC)
        rows = (
            await self._db.scalars(
                select(SessionModel)
                .where(
                    SessionModel.user_id == user_id,
                    SessionModel.revoked_at.is_(None),
                    SessionModel.expires_at > now,
                )
                .order_by(SessionModel.last_active_at.desc())
            )
        ).all()
        return [_to_record(r) for r in rows]

    async def create(
        self,
        *,
        user_id: UUID,
        family_id: UUID,
        refresh_hash: str,
        expires_at: datetime,
        device_name: str | None,
        ip_address: str | None,
        user_agent: str | None,
    ) -> SessionRecord:
        model = SessionModel(
            user_id=user_id,
            family_id=family_id,
            refresh_hash=refresh_hash,
            expires_at=expires_at,
            device_name=device_name,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self._db.add(model)
        await self._db.flush()
        return _to_record(model)

    async def rotate(self, session_id: UUID, at: datetime) -> bool:
        result = await self._db.execute(
            update(SessionModel)
            .where(
                SessionModel.id == session_id,
                SessionModel.revoked_at.is_(None),
            )
            .values(replaced_at=at, revoked_at=at)
        )
        return result.rowcount > 0

    async def revoke(self, session_id: UUID, user_id: UUID, at: datetime) -> bool:
        result = await self._db.execute(
            update(SessionModel)
            .where(
                SessionModel.id == session_id,
                SessionModel.user_id == user_id,
                SessionModel.revoked_at.is_(None),
            )
            .values(revoked_at=at)
        )
        return result.rowcount > 0

    async def revoke_family(self, family_id: UUID, at: datetime) -> int:
        result = await self._db.execute(
            update(SessionModel)
            .where(
                SessionModel.family_id == family_id,
                SessionModel.revoked_at.is_(None),
            )
            .values(revoked_at=at)
        )
        return result.rowcount

    async def revoke_all(self, user_id: UUID, at: datetime) -> int:
        result = await self._db.execute(
            update(SessionModel)
            .where(
                SessionModel.user_id == user_id,
                SessionModel.revoked_at.is_(None),
            )
            .values(revoked_at=at)
        )
        return result.rowcount

    async def touch(
        self, session_id: UUID, at: datetime, *, stale_before: datetime
    ) -> bool:
        result = await self._db.execute(
            update(SessionModel)
            .where(
                SessionModel.id == session_id,
                SessionModel.last_active_at < stale_before,
            )
            .values(last_active_at=at)
        )
        return result.rowcount > 0

    async def cleanup_expired(self, now: datetime) -> int:
        result = await self._db.execute(
            delete(SessionModel).where(SessionModel.expires_at < now)
        )
        return result.rowcount
