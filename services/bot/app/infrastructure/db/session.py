from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import get_settings

settings = get_settings()


def _build_engine() -> AsyncEngine:
    engine_kwargs: dict = {
        "echo": settings.sql_echo,
        "pool_pre_ping": settings.db_pool_pre_ping,
    }

    database_url = settings.database_url.lower()
    if not database_url.startswith("sqlite"):
        engine_kwargs["pool_size"] = settings.db_pool_size
        engine_kwargs["max_overflow"] = settings.db_max_overflow

    return create_async_engine(
        settings.database_url,
        **engine_kwargs,
    )


engine: AsyncEngine = _build_engine()

SessionFactory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with SessionFactory() as session:
        try:
            yield session
        finally:
            await session.close()
