
"""Async SQLAlchemy engine and session factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings


def _build_engine() -> AsyncEngine:
    """Create the async database engine."""
    kwargs: dict[str, Any] = {
        "pool_pre_ping": True,
    }

    # Connection pool settings are useful for PostgreSQL.
    if not settings.IS_SQLITE:
        kwargs["pool_size"] = 10
        kwargs["max_overflow"] = 20

    return create_async_engine(
        settings.DATABASE_URL,
        echo=settings.DEBUG,
        **kwargs,
    )


# Database engine
engine: AsyncEngine = _build_engine()


# Database session factory
AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency that provides a database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """Provide a session for scripts and background tasks."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def dispose_engine() -> None:
    """Close database connections during application shutdown."""
    await engine.dispose()
