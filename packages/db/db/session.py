"""Async SQLAlchemy engine + session factory.

The engine is process-global and lazy: first call to `get_engine` creates it;
subsequent calls return the cached instance. Tests override `DATABASE_URL` via
env before importing.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def get_engine(url: str | None = None) -> AsyncEngine:
    global _engine
    if _engine is None:
        db_url = url or os.environ.get(
            "DATABASE_URL",
            "postgresql+asyncpg://cogency:cogency_dev@localhost:5432/cogency",
        )
        _engine = create_async_engine(db_url, pool_pre_ping=True, future=True)
    return _engine


def get_sessionmaker(url: str | None = None) -> async_sessionmaker[AsyncSession]:
    global _sessionmaker
    if _sessionmaker is None:
        _sessionmaker = async_sessionmaker(get_engine(url), expire_on_commit=False)
    return _sessionmaker


@asynccontextmanager
async def async_session(url: str | None = None) -> AsyncIterator[AsyncSession]:
    sm = get_sessionmaker(url)
    async with sm() as session:
        yield session


async def dispose_engine() -> None:
    global _engine, _sessionmaker
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _sessionmaker = None
