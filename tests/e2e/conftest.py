import os

import pytest_asyncio
import sqlalchemy
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from core.models import Base

TEST_DB_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://tematch:tematch@localhost:5432/tematch_test",
)


@pytest_asyncio.fixture
async def engine():
    eng = create_async_engine(TEST_DB_URL, pool_size=1, max_overflow=0)
    async with eng.begin() as conn:
        await conn.execute(sqlalchemy.text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await eng.dispose()


@pytest_asyncio.fixture
async def connection(engine):
    """Connection wrapped in a transaction that gets rolled back after each test."""
    async with engine.connect() as conn:
        trans = await conn.begin()
        yield conn
        await trans.rollback()


@pytest_asyncio.fixture
async def session(connection):
    """Session where commit() becomes a savepoint — rolled back after test."""
    sess = AsyncSession(bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False)
    yield sess
    await sess.close()


@pytest_asyncio.fixture
async def session_factory(connection):
    """Factory returning sessions bound to the same rolled-back transaction."""

    class _Factory:
        def __call__(self):
            return _CM(connection)

    class _CM:
        def __init__(self, conn):
            self._session = AsyncSession(
                bind=conn, join_transaction_mode="create_savepoint", expire_on_commit=False
            )

        async def __aenter__(self):
            return self._session

        async def __aexit__(self, *args):
            await self._session.close()

    return _Factory()
