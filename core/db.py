# core/db.py
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.config import Settings


def create_engine(settings: Settings):
    return create_async_engine(settings.DATABASE_URL, echo=False)


def create_session_factory(engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)
