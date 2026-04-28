"""FastAPI dependencies: DB session, Temporal client.

Both are lazy + cached on the app object via the lifespan handler so individual
requests get a cheap pointer.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from temporalio.client import Client as TemporalClient

from db import async_session

from app.config import Settings, get_settings


async def db_session() -> AsyncIterator[AsyncSession]:
    settings = get_settings()
    async with async_session(settings.database_url) as session:
        yield session


def settings_dep(settings: Settings = Depends(get_settings)) -> Settings:
    return settings


async def temporal_client(request: Request) -> TemporalClient:
    """Cached on app.state — created once per process at lifespan startup."""
    return request.app.state.temporal
