"""SQLAlchemy adapter for the OAuthIdentityRepository protocol."""
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from forge_api.domain.users import OAuthIdentityRecord
from forge_api.infrastructure.database.models import OAuthIdentityModel


def _to_record(model: OAuthIdentityModel) -> OAuthIdentityRecord:
    return OAuthIdentityRecord(
        id=model.id,
        user_id=model.user_id,
        provider=model.provider,
        subject=model.subject,
        created_at=model.created_at,
    )


class SqlOAuthIdentityRepository:
    """Concrete SQLAlchemy implementation of ``OAuthIdentityRepository``."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def find(self, provider: str, subject: str) -> OAuthIdentityRecord | None:
        model = await self._db.scalar(
            select(OAuthIdentityModel).where(
                OAuthIdentityModel.provider == provider,
                OAuthIdentityModel.subject == subject,
            )
        )
        return _to_record(model) if model else None

    async def create(
        self, *, user_id: UUID, provider: str, subject: str
    ) -> OAuthIdentityRecord:
        model = OAuthIdentityModel(
            user_id=user_id,
            provider=provider,
            subject=subject,
        )
        self._db.add(model)
        await self._db.flush()
        return _to_record(model)
