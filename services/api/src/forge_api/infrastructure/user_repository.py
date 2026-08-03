"""SQLAlchemy adapter for the UserRepository protocol."""
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from forge_api.domain.users import UserRecord
from forge_api.infrastructure.database.models import UserModel


def _to_record(model: UserModel) -> UserRecord:
    return UserRecord(
        id=model.id,
        email=model.email,
        password_hash=model.password_hash,
        created_at=model.created_at,
    )


class SqlUserRepository:
    """Concrete SQLAlchemy implementation of ``UserRepository``."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def find_by_email(self, email: str) -> UserRecord | None:
        model = await self._db.scalar(
            select(UserModel).where(UserModel.email == email.lower())
        )
        return _to_record(model) if model else None

    async def find_by_id(self, user_id: UUID) -> UserRecord | None:
        model = await self._db.get(UserModel, user_id)
        return _to_record(model) if model else None

    async def create(self, *, email: str, password_hash: str | None) -> UserRecord:
        model = UserModel(email=email.lower(), password_hash=password_hash)
        self._db.add(model)
        await self._db.flush()
        return _to_record(model)
