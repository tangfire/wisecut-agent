"""Synchronous database helpers for the API process.

The API process uses synchronous SQLAlchemy sessions to avoid the
asyncpg event loop conflict under uvicorn/anyio in Docker.  The Worker
process continues to use asyncpg + async SQLAlchemy in its own event loop.
"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app.settings import settings as _default_settings

_engine = None
_session_factory = None
_settings = _default_settings


def configure_sync_engine(new_settings) -> None:
    """Update the settings reference and reset cached engine/session factory.

    Call this in test fixtures to point the sync engine at the test database.
    """
    global _settings, _engine, _session_factory
    _settings = new_settings
    _engine = None
    _session_factory = None


def get_sync_engine():
    """Get or create the synchronous SQLAlchemy engine."""
    global _engine
    if _engine is None:
        url = _settings.database_url
        if "+aiosqlite" in url:
            url = url.replace("+aiosqlite", "")
        elif "+asyncpg" in url:
            url = url.replace("+asyncpg", "")

        # In-memory SQLite creates a new DB per connection. For tests that
        # need to share state with the async engine, use a file-based DB.
        is_sqlite_mem = url == "sqlite:///:memory:"
        if is_sqlite_mem:
            url = "sqlite:///./.test_shared.db"

        kwargs = {
            "echo": _settings.debug,
            "pool_recycle": 3600,
        }
        if not (is_sqlite_mem or url.startswith("sqlite")):
            kwargs["pool_size"] = _settings.db_pool_size
            kwargs["max_overflow"] = _settings.db_max_overflow
        else:
            kwargs["poolclass"] = NullPool

        _engine = create_engine(url, **kwargs)
    return _engine


def get_sync_session_factory() -> sessionmaker:
    """Get or create the synchronous session factory."""
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(
            get_sync_engine(),
            expire_on_commit=False,
        )
    return _session_factory


def get_sync_session():
    """Context manager: yields a synchronous DB session."""
    factory = get_sync_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def close_sync_db() -> None:
    """Dispose of the sync engine."""
    global _engine, _session_factory
    if _engine:
        _engine.dispose()
        _engine = None
        _session_factory = None

