from datetime import UTC, datetime
from uuid import UUID
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from forge_api.infrastructure.database.models import SessionModel
class SessionRepository:
    def __init__(self, session: AsyncSession): self._session=session
    async def list_active(self,user_id: UUID): return list((await self._session.scalars(select(SessionModel).where(SessionModel.user_id==user_id,SessionModel.revoked_at.is_(None),SessionModel.expires_at>datetime.now(UTC)).order_by(SessionModel.last_active_at.desc()))).all())
    async def revoke(self,session_id: UUID,user_id: UUID): return await self._session.execute(update(SessionModel).where(SessionModel.id==session_id,SessionModel.user_id==user_id,SessionModel.revoked_at.is_(None)).values(revoked_at=datetime.now(UTC)))
    async def revoke_all(self,user_id: UUID): return await self._session.execute(update(SessionModel).where(SessionModel.user_id==user_id,SessionModel.revoked_at.is_(None)).values(revoked_at=datetime.now(UTC)))
    async def cleanup(self): return await self._session.execute(delete(SessionModel).where(SessionModel.expires_at<datetime.now(UTC)))
