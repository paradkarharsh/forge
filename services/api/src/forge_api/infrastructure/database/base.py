from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from forge_api.infrastructure.settings import Settings


class Base(DeclarativeBase):
    pass


def create_engine(settings: Settings) -> AsyncEngine:
    return create_async_engine(str(settings.database_url), pool_pre_ping=True)


def create_session_factory(settings: Settings) -> async_sessionmaker:
    return async_sessionmaker(create_engine(settings), expire_on_commit=False)
