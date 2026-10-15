"""SQLAlchemy async engine and session factory.

Note on asyncpg + uvicorn event loop compatibility:
  asyncpg's connection pool binds its background tasks to the event loop that
  exists at pool initialization time.  If the pool is first accessed from a
  different loop (e.g. Starlette middleware context), subsequent queries raise
  "Future attached to a different loop".  We therefore eagerly initialize the
  pool during application startup, which runs in the main asyncio loop.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.settings import settings

_engine: AsyncEngine | None = None
_async_session_factory: sessionmaker[AsyncSession] | None = None
_pool_ready = False


def get_engine() -> AsyncEngine:
    global _engine, _pool_ready
    if _engine is None:
        # SQLite (including aiosqlite) does not support pool_size/max_overflow.
        if settings.database_url.startswith("sqlite"):
            _engine = create_async_engine(
                settings.database_url,
                echo=settings.debug,
            )
            _pool_ready = True
        else:
            # pool_pre_ping disabled: causes event loop conflicts with asyncpg
            # under uvicorn/anyio in some environments (Docker).
            _engine = create_async_engine(
                settings.database_url,
                pool_size=settings.db_pool_size,
                max_overflow=settings.db_max_overflow,
                pool_recycle=3600,
                echo=settings.debug,
            )
    return _engine


async def ensure_pool_initialized() -> None:
    """Eagerly initialize the asyncpg connection pool in the current event loop.

    Must be called from the main application event loop (e.g. lifespan startup).
    """
    global _pool_ready
    if _pool_ready:
        return
    engine = get_engine()
    try:
        async with engine.connect() as conn:
            await conn.execute("SELECT 1")
        _pool_ready = True
    except Exception:
        # If the check fails (e.g. DB not yet ready), leave pool uninitialized;
        # the next call will retry.
        pass


def get_session_factory() -> sessionmaker[AsyncSession]:
    global _async_session_factory
    if _async_session_factory is None:
        _async_session_factory = sessionmaker(
            get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _async_session_factory


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: yields an async DB session."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def close_db() -> None:
    """Dispose of the engine. Call on shutdown."""
    global _engine, _async_session_factory
    if _engine:
        await _engine.dispose()
        _engine = None
        _async_session_factory = None
