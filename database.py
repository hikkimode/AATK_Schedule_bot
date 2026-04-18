from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from models import Base

# Global engine reference for cleanup
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def create_engine_and_sessionmaker(database_url: str) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    """Create database engine and session factory with optimized settings."""
    global _engine, _session_factory
    
    _engine = create_async_engine(
        database_url,
        connect_args={
            "prepared_statement_cache_size": 0,
            "statement_cache_size": 0
        },
        pool_pre_ping=True,
        pool_recycle=300,
        pool_size=10,
        max_overflow=20,
        echo=False  # Set to True for debugging SQL queries
    )
    _session_factory = async_sessionmaker(
        _engine,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False
    )
    return _engine, _session_factory


async def init_database(engine: AsyncEngine) -> None:
    """Initialize database tables."""
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


async def dispose_engine() -> None:
    """Gracefully dispose of database engine and close all connections."""
    global _engine
    
    if _engine is not None:
        logger.info("Disposing database engine and closing connections...")
        await _engine.dispose()
        _engine = None
        logger.info("Database engine disposed successfully")


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Context manager for database sessions with automatic cleanup."""
    if _session_factory is None:
        raise RuntimeError("Database not initialized. Call create_engine_and_sessionmaker first.")
    
    session = _session_factory()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def health_check() -> bool:
    """Check database connectivity."""
    if _engine is None:
        return False
    
    try:
        from sqlalchemy import text
        async with _engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False
