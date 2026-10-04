"""Async SQLAlchemy engine and session factory.

Exposes:
  * ``engine``            — the process-wide AsyncEngine.
  * ``AsyncSessionLocal`` — a sessionmaker bound to that engine.
  * ``get_session``       — FastAPI dependency yielding a session (auto-rollback
                            on error, close on exit).
  * ``session_scope``     — an explicit async context manager for scripts/services.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings


def _build_engine() -> AsyncEngine:
    """Create the async engine, applying pool settings only where supported."""
    kwargs: dict = {
        "echo": settings.db_echo,
        "pool_pre_ping": True,
        "future": True,
    }
    # SQLite (used in tests) does not accept Postgres pool sizing args.
    if not settings.is_sqlite:
        kwargs["pool_size"] = settings.db_pool_size
        kwargs["max_overflow"] = settings.db_max_overflow

    return create_async_engine(settings.database_url, **kwargs)


engine: AsyncEngine = _build_engine()

AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: yield a session, rolling back on unhandled errors."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """Context manager for non-request code (scripts, startup tasks)."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def dispose_engine() -> None:
    """Dispose the engine's connection pool (call on shutdown)."""
    await engine.dispose()
