"""Database setup and session management using SQLAlchemy async."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from backend.config import settings


class Base(DeclarativeBase):
    pass


engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    connect_args={
        "timeout": 30,
        "check_same_thread": False,
    },
    pool_pre_ping=True,
)


async_session = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def init_db() -> None:
    """Create all database tables and configure SQLite for concurrency."""

    from backend.models import agent, command, conversation, goal, memory, production_cycle, production_operation, youtube_performance_snapshot  # noqa: F401

    async with engine.begin() as conn:
        # Enable WAL mode so reads can continue while another connection writes.
        await conn.exec_driver_sql("PRAGMA journal_mode=WAL")

        # Wait up to 30 seconds when another SQLite transaction is writing.
        await conn.exec_driver_sql("PRAGMA busy_timeout=30000")

        # Keep foreign-key enforcement enabled.
        await conn.exec_driver_sql("PRAGMA foreign_keys=ON")

        await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency that provides a database session."""

    async with async_session() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

